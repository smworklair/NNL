# -*- coding: utf-8 -*-
"""Клиент внешних моделей для NNL. Только стандартная библиотека.

Единый транспорт для всех провайдеров: один вызов POST {base_url}/chat/completions
в формате, совместимом с OpenAI. Описание провайдеров читается из файла
провайдеры.json рядом с этим файлом, ключи в нём не хранятся.

Что сохраняется от прежней версии:
  * ключи читаются из файла NNL_KEY_FILE (по умолчанию C:\\KEY CLAUDE\\KEY.txt) или из переменных окружения;
    ключ нигде не печатается, не пишется в журнал и вырезается из текстов ошибок;
  * кэш по хешу запроса (повтор того же запроса не уходит наружу): ~/.nnl/кэш_моделей.jsonl;
    формат ключа кэша для запросов без инструментов оставлен прежним, чтобы старые записи продолжали находиться;
  * пул моделей вида «модель_а|модель_б» с переходом на следующую при ошибке превышения лимита;
  * ожидание при ошибке 429 по заголовку Retry-After и по тексту ответа, честное время вместе с ожиданием;
  * учёт вызовов, токенов и задержек (`СЧЁТ`, `ЖУРНАЛ`), структурный вывод по схеме, поддержка инструментов.
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

ФАЙЛ_КЛЮЧЕЙ = os.environ.get("NNL_KEY_FILE", r"C:\KEY CLAUDE\KEY.txt")
КЭШ_ФАЙЛ = os.path.join(os.path.expanduser("~"), ".nnl", "кэш_моделей.jsonl")
ПРОВАЙДЕРЫ_ФАЙЛ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "провайдеры.json")
UA = {"User-Agent": "Mozilla/5.0 NNL-lab"}
_замок = threading.Lock()
_кэш = None
_провайдеры = None
СЧЁТ = {}          # провайдер -> {вызовов, из_кэша, ошибок, токены_вход, токены_выход, мс}
ЖУРНАЛ = []        # последние вызовы без текста запроса: провайдер, модель, мс, токены, кэш
_свой = threading.local()   # журнал вызовов текущего потока: ходы разных чатов идут параллельно и не должны видеть чужие вызовы


def метка_журнала():
    return len(_свой.__dict__.setdefault("в", []))


def вызовы_после(метка):
    return _свой.__dict__.setdefault("в", [])[метка:]


class Ошибка(Exception):
    pass


class Лимит(Ошибка):
    """Лимит запросов/токенов в минуту: ждать столько-то секунд (используется пулом моделей)."""

    def __init__(self, ждать):
        super().__init__("лимит, ждать %.1f с" % ждать)
        self.ждать = ждать


def _загрузить_провайдеры():
    global _провайдеры
    if _провайдеры is None:
        with open(ПРОВАЙДЕРЫ_ФАЙЛ, encoding="utf-8") as f:
            _провайдеры = json.load(f)
    return _провайдеры


def конфиг_провайдера(провайдер):
    return _загрузить_провайдеры().get(провайдер)


def _скрыть_ключ(текст, ключ):
    if not текст or not ключ:
        return текст
    return str(текст).replace(ключ, "<ключ>")


def _ключи():
    k = {}
    try:
        провайдеры = _загрузить_провайдеры()
    except Exception:  # noqa: BLE001
        провайдеры = {}
    строки = []
    if os.path.exists(ФАЙЛ_КЛЮЧЕЙ):
        with open(ФАЙЛ_КЛЮЧЕЙ, "rb") as f:
            строки = [l.strip() for l in f.read().decode("utf-8-sig").splitlines()]
    нижние = [l.lower() for l in строки]
    for пров, cfg in провайдеры.items():
        try:
            метка = cfg.get("ключ_метка") if isinstance(cfg, dict) else None
        except Exception:  # noqa: BLE001
            метка = None
        if метка:
            цель = str(метка).lower()
            найден = None
            for i, l in enumerate(нижние):
                if l == цель and i + 1 < len(строки) and строки[i + 1]:
                    найден = строки[i + 1]
            if найден:
                k[пров] = найден
        env = None
        try:
            env = cfg.get("ключ_env") if isinstance(cfg, dict) else None
        except Exception:  # noqa: BLE001
            env = None
        if env and os.environ.get(env):
            k[пров] = os.environ[env].strip()
    return k


def есть_ключ(провайдер):
    cfg = None
    try:
        cfg = конфиг_провайдера(провайдер)
    except Exception:  # noqa: BLE001
        cfg = None
    if cfg is None:
        return False
    if cfg.get("подключён") is False:
        return False
    if not cfg.get("авторизация"):
        return True
    return ключ_провайдера(провайдер) is not None


def ключ_провайдера(провайдер):
    return _ключи().get(провайдер)


def _загрузить_кэш():
    global _кэш
    if _кэш is None:
        _кэш = {}
        if os.path.exists(КЭШ_ФАЙЛ):
            with open(КЭШ_ФАЙЛ, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                        _кэш[r["ключ"]] = r["ответ"]
                    except Exception:  # noqa: BLE001
                        pass
    return _кэш


def _записать_кэш(ключ, ответ):
    os.makedirs(os.path.dirname(КЭШ_ФАЙЛ), exist_ok=True)
    with open(КЭШ_ФАЙЛ, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ключ": ключ, "ответ": ответ}, ensure_ascii=False) + "\n")


def _имя_схемы_безопасное(имя):
    чистое = re.sub(r"[^a-zA-Z0-9_-]", "_", str(имя or "answer")) or "answer"
    return чистое[:64]


ЦЕНЫ = {}  # цены провайдеров пока не заданы; запись остаётся, чтобы учёт не падал


def цена(модель, т_вх, т_вых):
    p = ЦЕНЫ.get(str(модель).partition("@")[0])
    return round((т_вх * p[0] + т_вых * p[1]) / 1e6, 6) if p else None


def цена_строкой(usd, неполная=False):
    if usd is None:
        return "н/д"
    if неполная:
        return "$%.4f (неполная)" % usd
    return "$%.4f" % usd


def _учесть(провайдер, модель, мс, т_вх, т_вых, из_кэша=False, ошибка=False, повторов=0, usd=None, т_рас=None):
    with _замок:
        c = СЧЁТ.setdefault(провайдер, {"вызовов": 0, "из_кэша": 0, "ошибок": 0, "токены_вход": 0, "токены_выход": 0, "мс": 0, "usd": 0.0, "usd_неполная": False})
        if ошибка:
            c["ошибок"] += 1
        elif из_кэша:
            c["из_кэша"] += 1
        else:
            c["вызовов"] += 1
            c["токены_вход"] += т_вх or 0
            c["токены_выход"] += т_вых or 0
            c["мс"] += мс
            if usd is None:
                c["usd_неполная"] = True
            else:
                c["usd"] = round(c.get("usd", 0.0) + usd, 6)
        запись = {"провайдер": провайдер, "модель": модель, "мс": мс, "вход": т_вх, "выход": т_вых, "кэш": из_кэша, "ошибка": ошибка, "повторов": повторов, "usd": usd,
                  "т_рассуждения": т_рас}
        ЖУРНАЛ.append(запись)
        _свой.__dict__.setdefault("в", []).append(запись)
        del ЖУРНАЛ[:-500]


def _хеш_запроса(провайдер, модель, система, история, схема, температура, макс_токенов, размышление, tools=None, tool_choice=None, extra_body=None):
    if tools is None and tool_choice is None and extra_body is None:
        return hashlib.sha256(json.dumps([провайдер, модель, система, история, схема, температура, макс_токенов, размышление],
                                         ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return hashlib.sha256(json.dumps([провайдер, модель, система, история, схема, температура, макс_токенов, размышление, tools, tool_choice, extra_body],
                                     ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _в_сообщения(система, история):
    сообщения = []
    if система:
        сообщения.append({"role": "system", "content": система})
    for элемент in (история or []):
        if isinstance(элемент, dict):
            сообщения.append(dict(элемент))
            continue
        try:
            роль, текст = элемент[0], элемент[1]
        except Exception as e:  # noqa: BLE001
            raise Ошибка("история должна содержать пары (роль, текст) или готовые сообщения") from e
        if роль == "model":
            сообщения.append({"role": "assistant", "content": текст})
        elif роль in ("user", "system", "tool", "assistant"):
            сообщение = {"role": роль, "content": текст}
            if len(элемент) > 2 and isinstance(элемент[2], str) and элемент[2]:
                сообщение["tool_call_id"] = элемент[2]
            сообщения.append(сообщение)
        else:
            raise Ошибка("неизвестная роль в истории: %r" % (роль,))
    return сообщения


def _ждать_из_заголовка(заголовки):
    if not заголовки:
        return None
    имя = None
    try:
        имена = list(заголовки.keys())
    except Exception:  # noqa: BLE001
        return None
    for h in имена:
        if str(h).lower() == "retry-after":
            имя = h
            break
    if имя is None:
        return None
    try:
        сырое = заголовки.get(имя)
    except Exception:  # noqa: BLE001
        return None
    if сырое is None:
        return None
    сырое = str(сырое).strip()
    try:
        return max(0.0, min(float(сырое.split()[0]), 30.0))
    except Exception:  # noqa: BLE001
        return None


def _приложить_инструменты(тело, tools=None, tool_choice=None):
    if tools is not None:
        тело["tools"] = tools
    if tool_choice is not None:
        тело["tool_choice"] = tool_choice
    return тело


def спросить(провайдер, модель, система, история, схема=None, температура=0.2, макс_токенов=1500, таймаут=90,
             кэш=True, размышление=False, не_ждать=False, tools=None, tool_choice=None, extra_body=None, на_часть=None):
    """История: [(роль, текст)] где роль user|model, либо готовые dict сообщения OpenAI (нужны для инструментов).
    Возвращает dict: текст, данные (если была схема), tool_calls (если модель вернула вызовы), токены_вход/выход, мс, из_кэша.
    на_часть(частичный_текст) — только для свободного текста без схемы: зовётся по мере генерации (поток SSE), итог на странице виден сразу."""
    if "|" in str(модель):
        return _пул(провайдер, str(модель).split("|"), система, история, схема, температура, макс_токенов, таймаут, кэш, размышление,
                     tools=tools, tool_choice=tool_choice, extra_body=extra_body, на_часть=на_часть)
    if на_часть is not None and схема is None and tools is None and tool_choice is None:
        try:
            return _потоком(провайдер, модель, система, история, температура, макс_токенов, таймаут, кэш, размышление, extra_body, на_часть)
        except Exception:  # noqa: BLE001 — поток не удался (провайдер без SSE): обычный вызов ниже
            pass
    cfg = конфиг_провайдера(провайдер)
    if cfg is None:
        raise Ошибка("неизвестный провайдер %r" % провайдер)
    if cfg.get("подключён") is False:
        raise Ошибка("провайдер %s зарезервирован, но не подключён" % провайдер)
    хеш = _хеш_запроса(провайдер, модель, система, история, схема, температура, макс_токенов, размышление,
                        tools=tools, tool_choice=tool_choice, extra_body=extra_body)
    if кэш:
        с = _загрузить_кэш().get(хеш)
        if с is not None:
            _учесть(провайдер, модель, 0, 0, 0, из_кэша=True)
            ответ = dict(с)
            ответ.setdefault("tool_calls", None)
            ответ.setdefault("usd", None)
            ответ.setdefault("повторов", 0)
            return dict(ответ, из_кэша=True, мс=0)
    ключ = ключ_провайдера(провайдер)
    нужен_ключ = bool(cfg.get("авторизация"))
    if нужен_ключ and not ключ:
        raise Ошибка("нет ключа для %s (файл %s)" % (провайдер, ФАЙЛ_КЛЮЧЕЙ))
    base = str(cfg.get("base_url") or "").rstrip("/")
    if not base:
        raise Ошибка("у провайдера %s нет адреса base_url" % провайдер)
    url = base + "/chat/completions"
    сообщения = _в_сообщения(система, история)
    модель_для_апи = str(модель).partition("@")[0] or str(модель)
    тело = {"model": модель_для_апи, "messages": сообщения, "temperature": температура, "max_completion_tokens": макс_токенов}
    if схема:
        тело["response_format"] = {"type": "json_schema", "json_schema": {"name": _имя_схемы_безопасное("answer"), "schema": схема}}
    _приложить_инструменты(тело, tools, tool_choice)
    условие = None
    try:
        условие = (cfg.get("reasoning_effort_gpt_oss") or {}).get("условие_в_имени") or "gpt-oss"
    except Exception:  # noqa: BLE001
        условие = "gpt-oss"
    if условие and условие in str(модель):
        низкое, высокое = "low", "medium"
        try:
            пара = cfg.get("reasoning_effort_gpt_oss") or {}
            низкое = пара.get("без_размышления", низкое)
            высокое = пара.get("с_размышлением", высокое)
        except Exception:  # noqa: BLE001
            pass
        тело["reasoning_effort"] = высокое if размышление else низкое
    слитое = {}
    try:
        if isinstance(cfg.get("extra_body"), dict):
            слитое.update(cfg.get("extra_body"))
    except Exception:  # noqa: BLE001
        pass
    # «Глубже думать»: у провайдера может быть свой способ попросить рассуждение (extra_body_размышление в провайдеры.json).
    # Если провайдер такое поле не принял (HTTP 400), один раз повторяем без него: ответ важнее рассуждения.
    доп_размышления = {}
    if размышление and isinstance(cfg.get("extra_body_размышление"), dict):
        доп_размышления = dict(cfg["extra_body_размышление"])
        слитое.update(доп_размышления)
    if isinstance(extra_body, dict):
        слитое.update(extra_body)
    для_отката = {k_д: (cfg.get("extra_body") or {}).get(k_д) for k_д in доп_размышления}
    for k_д, v_д in слитое.items():
        if k_д not in тело:
            тело[k_д] = v_д
    заголовки = dict(UA, **{"Content-Type": "application/json"})
    if нужен_ключ:
        заголовки["Authorization"] = "Bearer " + ключ
    последняя = None
    ждать = 0.0
    t_всего, повторов = time.time(), 0
    for попытка in range(5):
        if ждать:
            time.sleep(ждать)
            повторов += 1
        ждать = (2, 5, 10, 15)[min(попытка, 3)]
        try:
            req = urllib.request.Request(url, data=json.dumps(тело, ensure_ascii=False).encode("utf-8"), headers=заголовки)
            with urllib.request.urlopen(req, timeout=таймаут) as r:
                d = json.load(r)
            мс = int(1000 * (time.time() - t_всего))      # со всеми ожиданиями лимита: это время, которое видит человек
            try:
                сообщение = (d.get("choices") or [{}])[0].get("message") or {}
            except Exception as e:  # noqa: BLE001
                raise Ошибка("пустой ответ сервера: нет choices") from e
            текст = сообщение.get("content") or ""
            рассуждение = сообщение.get("reasoning_content") or сообщение.get("reasoning") or ""
            м_думы = re.match(r"\s*<(think|thought)>(.*?)</\1>\s*", текст, re.S)      # часть провайдеров (Qwen на Groq, Gemini) кладёт рассуждение в сам текст
            if м_думы:
                рассуждение = рассуждение or м_думы.group(2).strip()
                текст = текст[м_думы.end():]
            вызовы = сообщение.get("tool_calls")
            u = d.get("usage", {}) or {}
            т_вх = u.get("prompt_tokens", 0) or 0
            т_вых = u.get("completion_tokens", 0) or 0
            т_рас = ((u.get("completion_tokens_details") or {}).get("reasoning_tokens")) or None
            остановка = None
            try:
                остановка = (d.get("choices") or [{}])[0].get("finish_reason")
            except Exception:  # noqa: BLE001
                остановка = None
            данные = None
            if схема:
                try:
                    данные = json.loads(текст)
                except Exception as e:  # noqa: BLE001
                    raise Ошибка("ответ не JSON%s: %s" % (" (обрезан по лимиту токенов: рассуждение модели заняло весь лимит)" if остановка == "length" else "", _скрыть_ключ(текст[:120], ключ))) from e
            usd = цена(модель, т_вх, т_вых)
            res = {"текст": текст, "данные": данные, "tool_calls": вызовы, "токены_вход": т_вх, "токены_выход": т_вых, "мс": мс,
                   "провайдер": провайдер, "модель": модель, "повторов": повторов, "usd": usd, "остановка": остановка,
                   "рассуждение": рассуждение, "токены_рассуждения": т_рас}
            _учесть(провайдер, модель, мс, т_вх, т_вых, повторов=повторов, usd=usd, т_рас=т_рас)
            if кэш:
                _загрузить_кэш()[хеш] = res
                with _замок:
                    _записать_кэш(хеш, res)
            return dict(res, из_кэша=False)
        except urllib.error.HTTPError as e:
            try:
                сырое = e.read().decode("utf-8", "replace")[:600]
            except Exception:  # noqa: BLE001
                сырое = ""
            чистое = _скрыть_ключ(сырое, ключ) if нужен_ключ else сырое
            последняя = "HTTP %s: %s" % (e.code, чистое[:300])
            if e.code == 400 and доп_размышления:           # провайдер не принял просьбу о рассуждении: повторяем без неё
                for k_д, v_д in для_отката.items():
                    if v_д is None:
                        тело.pop(k_д, None)
                    else:
                        тело[k_д] = v_д
                доп_размышления, для_отката = {}, {}
                ждать = 0.0
                continue
            if e.code == 429:       # лимит токенов в минуту: сервер сам говорит, сколько ждать
                из_заголовка = None
                try:
                    из_заголовка = _ждать_из_заголовка(e.headers)
                except Exception:  # noqa: BLE001
                    из_заголовка = None
                if из_заголовка is not None:
                    ждать = min(из_заголовка + 0.7, 30.0)
                else:
                    m = re.search(r"try again in ([\d.]+)s", чистое) or re.search(r"retry in ([\d.]+)s", чистое)
                    if m:
                        ждать = min(float(m.group(1)) + 0.7, 30.0)
                if не_ждать:
                    raise Лимит(ждать)
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (TimeoutError, urllib.error.URLError, OSError) as e:
            последняя = "%s" % type(e).__name__
        except Ошибка as e:
            сырое = str(e)
            последняя = _скрыть_ключ(сырое, ключ) if нужен_ключ else сырое
            break
    _учесть(провайдер, модель, 0, 0, 0, ошибка=True)
    raise Ошибка(последняя or "неизвестная ошибка")


def _потоком(провайдер, модель, система, история, температура, макс_токенов, таймаут, кэш, размышление, extra_body, на_часть):
    """Потоковый вызов свободного текста (без схемы): куски SSE → на_часть(накопленный текст). Возвращает тот же dict, что спросить.
    Падает с исключением, если провайдер не отдал поток: вызывающий молча идёт обычным путём."""
    cfg = конфиг_провайдера(провайдер)
    if cfg is None or cfg.get("подключён") is False:
        raise Ошибка("нет провайдера")
    хеш = _хеш_запроса(провайдер, модель, система, история, None, температура, макс_токенов, размышление, extra_body=extra_body)
    if кэш:
        с = _загрузить_кэш().get(хеш)
        if с is not None:
            _учесть(провайдер, модель, 0, 0, 0, из_кэша=True)
            ответ = dict(с)
            ответ.setdefault("tool_calls", None)
            try:
                на_часть(ответ.get("текст") or "")
            except Exception:  # noqa: BLE001
                pass
            return dict(ответ, из_кэша=True, мс=0)
    ключ = ключ_провайдера(провайдер)
    нужен_ключ = bool(cfg.get("авторизация"))
    if нужен_ключ and not ключ:
        raise Ошибка("нет ключа")
    base = str(cfg.get("base_url") or "").rstrip("/")
    if not base:
        raise Ошибка("нет адреса")
    url = base + "/chat/completions"
    сообщения = _в_сообщения(система, история)
    модель_для_апи = str(модель).partition("@")[0] or str(модель)
    тело = {"model": модель_для_апи, "messages": сообщения, "temperature": температура, "max_completion_tokens": макс_токенов,
            "stream": True, "stream_options": {"include_usage": True}}
    условие = None
    try:
        условие = (cfg.get("reasoning_effort_gpt_oss") or {}).get("условие_в_имени") or "gpt-oss"
    except Exception:  # noqa: BLE001
        условие = "gpt-oss"
    if условие and условие in str(модель):
        try:
            пара = cfg.get("reasoning_effort_gpt_oss") or {}
            тело["reasoning_effort"] = пара.get("с_размышлением", "medium") if размышление else пара.get("без_размышления", "low")
        except Exception:  # noqa: BLE001
            pass
    слитое = {}
    try:
        if isinstance(cfg.get("extra_body"), dict):
            слитое.update(cfg.get("extra_body"))
    except Exception:  # noqa: BLE001
        pass
    if размышление and isinstance(cfg.get("extra_body_размышление"), dict):
        слитое.update(dict(cfg["extra_body_размышление"]))
    if isinstance(extra_body, dict):
        слитое.update(extra_body)
    for k_д, v_д in слитое.items():
        if k_д not in тело:
            тело[k_д] = v_д
    заголовки = dict(UA, **{"Content-Type": "application/json", "Accept": "text/event-stream"})
    if нужен_ключ:
        заголовки["Authorization"] = "Bearer " + ключ
    t0 = time.time()
    req = urllib.request.Request(url, data=json.dumps(тело, ensure_ascii=False).encode("utf-8"), headers=заголовки)
    куски, думы_ч, остановка, т_вх, т_вых, т_рас = [], [], None, 0, 0, None
    with urllib.request.urlopen(req, timeout=таймаут) as r:
        ctype = ""
        try:
            ctype = str(r.headers.get("Content-Type") or "")
        except Exception:  # noqa: BLE001
            ctype = ""
        if "text/event-stream" not in ctype and "event-stream" not in ctype:
            # часть провайдеров отдаёт поток без явного типа: смотрим первые байты
            pass
        буф = b""
        while True:
            кус = r.read(4096)
            if not кус:
                break
            буф += кус
            while b"\n" in буф:
                строка, буф = буф.split(b"\n", 1)
                строка = строка.strip()
                if not строка or строка.startswith(b":"):
                    continue
                if not строка.startswith(b"data:"):
                    continue
                данные = строка[5:].strip()
                if данные == b"[DONE]":
                    буф = b""
                    break
                try:
                    ч = json.loads(данные.decode("utf-8", "replace"))
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(ч.get("usage"), dict) and not ч.get("choices"):
                    u = ч["usage"] or {}
                    т_вх = u.get("prompt_tokens", 0) or 0
                    т_вых = u.get("completion_tokens", 0) or 0
                    try:
                        т_рас = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
                    except Exception:  # noqa: BLE001
                        т_рас = None
                    continue
                try:
                    выбор = (ч.get("choices") or [{}])[0]
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(выбор.get("usage"), dict):
                    u = выбор["usage"] or ч.get("usage") or {}
                    т_вх = u.get("prompt_tokens", т_вх) or т_вх
                    т_вых = u.get("completion_tokens", т_вых) or т_вых
                дельта = выбор.get("delta") or выбор.get("message") or {}
                if isinstance(дельта, dict):
                    к = дельта.get("content") or ""
                    р = дельта.get("reasoning_content") or дельта.get("reasoning") or ""
                    if к:
                        куски.append(к)
                        try:
                            на_часть("".join(куски))
                        except Exception:  # noqa: BLE001
                            pass
                    if р:
                        думы_ч.append(р)
                if выбор.get("finish_reason"):
                    остановка = выбор.get("finish_reason")
                if isinstance(ч.get("usage"), dict):
                    u = ч["usage"] or {}
                    т_вх = u.get("prompt_tokens", 0) or т_вх
                    т_вых = u.get("completion_tokens", 0) or т_вых
                    try:
                        т_рас = (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or т_рас
                    except Exception:  # noqa: BLE001
                        pass
            if буф.strip() == b"data: [DONE]":
                break
    текст = "".join(куски)
    if not текст:
        raise Ошибка("поток пуст")
    рассуждение = "".join(думы_ч)
    м_думы = re.match(r"\s*<(think|thought)>(.*?)</\1>\s*", текст, re.S)
    if м_думы:
        рассуждение = рассуждение or м_думы.group(2).strip()
        текст = текст[м_думы.end():]
    мс = int(1000 * (time.time() - t0))
    usd = цена(модель, т_вх, т_вых)
    res = {"текст": текст, "данные": None, "tool_calls": None, "токены_вход": т_вх, "токены_выход": т_вых, "мс": мс,
           "провайдер": провайдер, "модель": модель, "повторов": 0, "usd": usd, "остановка": остановка,
           "рассуждение": рассуждение, "токены_рассуждения": т_рас}
    _учесть(провайдер, модель, мс, т_вх, т_вых, повторов=0, usd=usd, т_рас=т_рас)
    if кэш:
        _загрузить_кэш()[хеш] = res
        with _замок:
            _записать_кэш(хеш, res)
    return dict(res, из_кэша=False)


def _пул(провайдер, модели, система, история, схема, температура, макс_токенов, таймаут, кэш, размышление,
         tools=None, tool_choice=None, extra_body=None, на_часть=None):
    t0 = time.time()
    for _ in range(3):
        ждать = []
        for м in модели:
            try:
                r = спросить(провайдер, м, система, история, схема, температура, макс_токенов, таймаут, кэш, размышление, не_ждать=True,
                             tools=tools, tool_choice=tool_choice, extra_body=extra_body, на_часть=на_часть)
            except Лимит as e:
                ждать.append(e.ждать)
                continue
            if not r.get("из_кэша"):                     # честное время: вместе с переключениями между моделями
                r["мс"] = int(1000 * (time.time() - t0))
                своё = _свой.__dict__.setdefault("в", [])
                if своё:
                    своё[-1]["мс"] = r["мс"]
            return r
        time.sleep(min(ждать or [5.0]))
    raise Ошибка("лимиты всех моделей пула исчерпаны: " + ", ".join(модели))


def итоги():
    with _замок:
        return json.loads(json.dumps(СЧЁТ))
