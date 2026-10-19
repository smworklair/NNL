# -*- coding: utf-8 -*-
"""Сайт «Справка по годности»: мобильная страница и бэкенд NNL. Запуск: python сервер.py [порт=8090] [хост=127.0.0.1]

Страница и статика лежат рядом с этим файлом; бэкенд — в NNL/диалог, ядро NNL — в v8.
Сервер отдаёт сайт и API: статьи Расписания, умный поиск блоками, пороги, читалку и диалог.

Конечные точки:
  GET  /                      мобильная страница сайта
  GET  /<файл>                статика сайта (.html/.css/.js/.json/.svg/.png/.ico)
  GET  /api/config            пресеты и роли по умолчанию
  GET  /api/модели            все модели из провайдеры.json (с признаком «ключ есть») и пресеты
  GET  /api/totals            счётчики вызовов по провайдерам
  GET  /api/журнал            последние вызовы моделей (без текста запросов)
  GET  /api/статьи            список статей Расписания;  /api/статья?ид=34 — одна статья;  /api/поиск?q=...
  POST /api/turn              ход диалога  {сессия, режим: nnl|ядро|база, текст, роли?, глубже?}; nnl — только ядро без моделей, ядро — NNL+API, база — только модель
  POST /api/turn_stream       то же, но шаги следа приходят по мере работы строками JSON
  POST /api/событие           {сессия, события: [{время, тип, цель, значение}]} — нажатия и выбор на странице в журнал наблюдения
  GET  /api/наблюдение/сессии     сессии из журнала;  /api/наблюдение/сессия?id=...  хронология, проверки и метрики одной сессии
  POST /api/читатель         вопрос к модели по статье с проверкой цитат  {ид, вопрос, модель?, выделено?}
  GET  /api/ст34             диапазоны близорукости из текста статьи и результат по дптр
  GET  /api/пороги           калькуляторы порогов статьи  ?ид=34&...
  GET  /api/умныйпоиск      поиск блоками «здоровье» и «право»  ?q=...
  GET  /api/провайдеры       провайдеры для подключения своего ключа
  POST /api/ключ/проверка    проверка своего ключа без расхода токенов"""
import http.server
import json
import os
import socket
import socketserver
import sys
import re
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

КАТАЛОГ = os.path.dirname(os.path.abspath(__file__))
БЭКЕНД = os.path.join(КАТАЛОГ, "NNL", "диалог")
for п in (БЭКЕНД, КАТАЛОГ):
    if п not in sys.path:
        sys.path.insert(0, п)
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import диалог as Д  # noqa: E402
import клиент as К  # noqa: E402
import знания as З  # noqa: E402
import ссылки as С  # noqa: E402
import наблюдение as Н  # noqa: E402
import пороги as ПР  # noqa: E402

СТРАНИЦА = os.path.join(КАТАЛОГ, "вариация_1_кирпичи_десктоп.html")
СИСТЕМА = None
СЕССИИ = {}
_ЗАМКИ_СЕССИЙ = {}
_ЗАМОК_ЗАМКОВ = threading.Lock()
_СТАТИКА = {".html": "text/html", ".css": "text/css", ".js": "application/javascript",
            ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
            ".ico": "image/x-icon", ".webp": "image/webp", ".woff2": "font/woff2"}
_СТАТИКА_ПАПКИ = ("архив",)          # вложенная статика: только эти папки, только файлы внутри


def замок_сессии(ид):
    """Ходы одного чата идут по очереди, разных чатов — параллельно: медленный ответ одного API не держит остальные."""
    with _ЗАМОК_ЗАМКОВ:
        return _ЗАМКИ_СЕССИЙ.setdefault(str(ид), threading.Lock())
ДОП_МОДЕЛИ = {"groq": ["openai/gpt-oss-20b"], "gemini": ["gemini-3.1-flash-lite"]}
РОЛИ_ИМЕНА = ("разбор", "вопросы", "итог", "речь", "базовая")

СИСТЕМА_ЧИТАТЕЛЯ = """Ты помогаешь читать одну статью Расписания болезней (ПП РФ № 565, ред. 2026). Отвечай ТОЛЬКО по тексту статьи ниже.
Правила:
- Если в статье нет ответа, так и скажи: «в этой статье этого нет». Не додумывай, не дополняй знаниями извне.
- Для призывника берёшь графу I; графы II и III не упоминай, если об этом не спросили.
- Каждое утверждение привязывай к месту в документе: пиши «ст. N п. «буква»». В поле «цитаты» дай дословные короткие фрагменты статьи (не пересказ), на которые опираешься.
- Числа и пороги бери только из текста статьи. «Более X» — строго больше X; «до Y» — включая Y.
"""

СХЕМА_ЧИТАТЕЛЯ = {"type": "object", "properties": {
    "ответ": {"type": "string"},
    "цитаты": {"type": "array", "items": {"type": "object", "properties": {"пункт": {"type": "string"}, "текст": {"type": "string"}}, "required": ["пункт", "текст"]}}},
    "required": ["ответ", "цитаты"]}


def получить_сессии(ид):
    if ид not in СЕССИИ:
        СЕССИИ[ид] = {"nnl": СИСТЕМА.сессия(), "ядро": СИСТЕМА.сессия(), "база": СИСТЕМА.сессия(), "свободно": СИСТЕМА.сессия()}
    return СЕССИИ[ид]


def _роли_из_запроса(д):
    р = д.get("роли")
    if not isinstance(р, dict):
        return None
    out = {}
    for имя in РОЛИ_ИМЕНА:
        пара = р.get(имя)
        if not (isinstance(пара, (list, tuple)) and len(пара) == 2 and К.конфиг_провайдера(str(пара[0])) and str(пара[1]).strip()):
            return None
        out[имя] = (str(пара[0]), str(пара[1]).strip())
    return out


_НЕ_ЧАТ = re.compile(r"embed|image|video|tts|asr|audio|realtime|transcri|rerank|ocr|translate|livetranslate|wan\d|flux|sdxl|whisper|guard|orpheus|moderation|imagen|veo|lyria|native-audio|computer-use|robotics|aqa|speech|vc-|-vl-ocr|live|tingwu|-mt-|character|ccai|-20\d\d-\d\d-\d\d$|-\d{4}$", re.I)
_ЖИВЫЕ = {}                       # провайдер -> {"время", "модели"}: списки моделей берутся у самих провайдеров (/models), без зашитых имён
_СРОК_ЖИВЫХ = 6 * 3600


def _запросить_список(пров):
    cfg = К.конфиг_провайдера(пров) or {}
    ключ = К.ключ_провайдера(пров)
    if not ключ or cfg.get("подключён") is False or not cfg.get("base_url"):
        return None
    req = urllib.request.Request(cfg["base_url"].rstrip("/") + "/models", headers={"Authorization": "Bearer " + ключ, "User-Agent": "Mozilla/5.0 NNL-lab"})
    try:
        данные = json.load(urllib.request.urlopen(req, timeout=25))
    except Exception:  # noqa: BLE001
        return None
    ид = sorted({str(m.get("id", "")).replace("models/", "") for m in (данные.get("data") or данные.get("models") or [])})
    return [x for x in ид if x and not _НЕ_ЧАТ.search(x)]


def обновить_живые(принудительно=False):
    for пров in К._загрузить_провайдеры():
        старое = _ЖИВЫЕ.get(пров)
        if not принудительно and старое and time.time() - старое["время"] < _СРОК_ЖИВЫХ:
            continue
        м = _запросить_список(пров)
        if м is not None:
            _ЖИВЫЕ[пров] = {"время": time.time(), "модели": м}


def список_моделей():
    out = []
    for пров, cfg in К._загрузить_провайдеры().items():
        if cfg.get("подключён") is False:
            continue
        имена = list(cfg.get("модели") or []) + ДОП_МОДЕЛИ.get(пров, []) + list((_ЖИВЫЕ.get(пров) or {}).get("модели", []))
        for м in имена:
            if not any(x["id"] == "%s:%s" % (пров, м) for x in out):
                out.append({"id": "%s:%s" % (пров, м), "провайдер": пров, "модель": м, "ключ": К.есть_ключ(пров)})
    return {"модели": out, "пресеты": {k: {r: list(v) for r, v in роли.items()} for k, роли in Д.ПРЕСЕТЫ.items()}}


def статья_json(ид):
    а = СИСТЕМА.база.статьи.get(ид)
    if а is None:
        return None
    return {"ид": а.ид, "название": а.название, "пункты": а.пункты, "примечания": [l for l in а.примечания if not l.startswith("(см. текст")],
            "числа": sorted(СИСТЕМА.база.числа_документа(ид))}


_СТОП_СЛОВА = {"меня", "мне", "есть", "очень", "сильно", "после", "когда", "этого", "такое", "который", "какая", "какой", "иногда", "часто", "давно", "опять"}


def _основы_слов(текст):
    """Основы (первые 5 букв) значимых слов: так «диабет» находит «диабета», а «колет» — нет."""
    return {w[:5] for w in re.findall(r"[а-я]{4,}", текст.lower().replace("ё", "е")) if w not in _СТОП_СЛОВА}


def умный_поиск(текст):
    """Поиск по Расписанию болезней и правовым темам блоками NNL. Состояния нет: каждый запрос оценивается отдельно, ничего в сессии не копится.
    Сверх ответа блоков: пункт, ближайший по словам (код_ответ.пункт_по_словам); расчёты по числам из фразы (пороги.из_слов);
    потолок уверенности, как в режиме «ядро» (диалог.py): одна короткая фраза без чисел и без слов врача не получает уверенности выше 0,45,
    кроме случая, когда все её значимые слова есть в тексте самой статьи."""
    текст = (текст or "").strip()[:300]
    if len(текст) < 2:
        return {"запрос": текст, "статьи": [], "право": [], "числа": [], "вне_темы": False, "ворота": None}
    cz, cp = СИСТЕМА.блоки.область(текст)
    числа = ПР.из_слов(СИСТЕМА.база, текст, СИСТЕМА.код_решатель)
    статьи, право = [], []
    p, p0 = СИСТЕМА.блоки.статьи(текст)
    лучшая = max(p.values()) if p else 0.0
    if cz > 0 or (cz > -2.5 and лучшая >= 0.2 and p0 < 0.5):      # короткая фраза с цифрой («сахар 9») ворота проходит чуть ниже нуля, но статья при этом явная
        скудно = len(текст.split()) < 5 and not re.search(r"\d", текст) and not Д._ВРАЧ.search(текст)
        основы = _основы_слов(текст)
        for ид, v in sorted(p.items(), key=lambda x: -x[1])[:8]:
            if v >= 0.03 or not статьи:
                а = СИСТЕМА.база.статьи[ид]
                слова_есть = bool(основы) and основы <= _основы_слов(а.название + " " + а.сырой)
                огр = скудно and not слова_есть and v > 0.45
                запись = {"ид": ид, "название": а.название, "p": round(v, 3), "p_показ": round(min(v, 0.45) if огр else v, 3), "ограничено": огр}
                пункт = СИСТЕМА.код_решатель.пункт_по_словам(ид, текст) if v >= 0.2 else None
                if пункт:
                    запись["пункт"] = пункт[0]
                статьи.append(запись)
    if cp > 0:
        лучшие, _ = СИСТЕМА.блоки.право(текст, топ=3)
        for ид, v in лучшие:
            if v >= 0.15 and ид in СИСТЕМА.база.темы:
                т = СИСТЕМА.база.темы[ид]
                право.append({"тема": ид, "название": т["название"], "суть": т["суть"], "p": round(v, 3)})
    подсказка = "Фраза короткая: добавьте диагноз, что сказал врач или измеренные значения — станет точнее." if статьи and статьи[0]["ограничено"] else ""
    return {"запрос": текст, "статьи": статьи[:6], "право": право[:2], "числа": числа, "подсказка": подсказка,
            "подтверждение": "врач" if Д._ВРАЧ.search(текст) else "слова",
            "вне_темы": not статьи and not право and not числа,
            "ворота": {"здоровье": round(cz, 2), "право": round(cp, 2)}}


def читатель(д):
    ид = str(д.get("ид", ""))
    а = СИСТЕМА.база.статьи.get(ид)
    if а is None:
        return {"ошибка": "нет статьи %s" % ид}
    вопрос = str(д.get("вопрос", "")).strip()
    if not вопрос:
        return {"ошибка": "пустой вопрос"}
    пров, _, мод = str(д.get("модель") or "%s:%s" % Д.РОЛИ["речь"]).partition(":")
    if not К.конфиг_провайдера(пров) or not мод:
        return {"ошибка": "неверная модель"}
    выделено = str(д.get("выделено", "")).strip()[:600]
    сообщение = ("Выделенный человеком фрагмент: «%s»\n\n" % выделено if выделено else "") + "Вопрос: " + вопрос
    r = К.спросить(пров, мод, СИСТЕМА_ЧИТАТЕЛЯ + "\n\n" + а.текст_для_модели(6000), [("user", сообщение)], схема=СХЕМА_ЧИТАТЕЛЯ, температура=0.2, макс_токенов=900, кэш=False)
    данные = r["данные"]
    if isinstance(данные, list) and данные and isinstance(данные[0], dict):
        данные = данные[0]
    ответ = str(данные.get("ответ", ""))
    цитаты = [{"пункт": str(ц.get("пункт", "")), "текст": str(ц.get("текст", "")), "подтверждена": С.цитата_в_статье(str(ц.get("текст", "")), а)} for ц in данные.get("цитаты", []) if isinstance(ц, dict)]
    разрешено = СИСТЕМА.база.числа_документа(ид) | З.нормализованные_числа(вопрос + " " + выделено)
    return {"ответ": ответ, "цитаты": цитаты, "ссылки": С.найти(ответ, СИСТЕМА.база), "охрана_чисел": Д.проверка_чисел(ответ, разрешено),
            "мс": r["мс"], "токены": r["токены_вход"] + r["токены_выход"], "модель": "%s:%s" % (пров, мод)}


_РЕГ_МОДЕЛИ = re.compile(r"^[A-Za-z0-9._:/@\-]{1,120}$")
_РЕГ_КЛЮЧА = re.compile(r"^[\x21-\x7e]{8,512}$")           # печатные символы без пробелов: заодно нельзя подсунуть перевод строки в заголовок


def личный_из_заголовков(заголовки):
    """Свой ключ человека из заголовков X-NNL-Provider / X-NNL-Model / X-NNL-Key. Только заголовки: тело запроса попадает в журналы, заголовки — нет.
    None — ключа нет; бросает ValueError, если заголовки неверные."""
    ключ = заголовки.get("X-NNL-Key")
    if not ключ:
        return None
    пров = (заголовки.get("X-NNL-Provider") or "").strip()
    модель = (заголовки.get("X-NNL-Model") or "").strip()
    cfg = К.конфиг_провайдера(пров)
    if not cfg or cfg.get("подключён") is False or not cfg.get("авторизация"):
        raise ValueError("провайдер для своего ключа не подходит")
    if not _РЕГ_КЛЮЧА.match(ключ):
        raise ValueError("ключ выглядит неверно")
    if not _РЕГ_МОДЕЛИ.match(модель):
        raise ValueError("имя модели выглядит неверно")
    return (пров, модель, ключ)


def провайдеры_для_ключа():
    out = []
    for имя, cfg in К._загрузить_провайдеры().items():
        if not isinstance(cfg, dict) or cfg.get("подключён") is False or not cfg.get("авторизация"):
            continue
        out.append({"имя": имя, "модели": list(cfg.get("модели") or []), "ключ_на_сервере": К.есть_ключ(имя), "документация": cfg.get("документация") or ""})
    return out


def ход(д, на_шаг=None, личный=None):
    """Один ход. на_шаг — функция(событие), куда сразу уходит каждый шаг следа (потоковая страница); без неё след приходит только в ответе."""
    с = получить_сессии(д["сессия"])[д["режим"]]
    if личный is not None:
        пров, модель, ключ = личный
        с.роли = {имя: (пров, модель) for имя in РОЛИ_ИМЕНА}          # все роли — на ту одну модель, к которой человек дал ключ
        с._личные_роли = True
        with К.личный_ключ(пров, ключ):
            return _ход_внутри(д, с, на_шаг)
    if getattr(с, "_личные_роли", False):                              # раньше в этой сессии были роли под чужой ключ: не оставляем их без ключа
        с.роли = None
        с._личные_роли = False
    return _ход_внутри(д, с, на_шаг)


def _ход_внутри(д, с, на_шаг):
    р = None if getattr(с, "_личные_роли", False) else _роли_из_запроса(д)
    if р:
        с.роли = р
    с.глубже = bool(д.get("глубже"))
    с.на_шаг = на_шаг
    try:
        т = {"nnl": с.ход_ядра, "ядро": с.ход, "база": с.ход_базовой, "свободно": с.ход_свободный}[д["режим"]](д["текст"])
    finally:
        с.на_шаг = None
    т["ссылки"] = С.найти(т.get("ответ", ""), СИСТЕМА.база)
    т["роли"] = {k: list(v) for k, v in (с.роли or Д.РОЛИ).items()}
    try:
        Н.записать_ход(д["сессия"], д["режим"], т["роли"], с.глубже, т)
    except Exception:  # noqa: BLE001 — журнал не должен ронять ответ
        traceback.print_exc()
    return т


class Обработчик(http.server.BaseHTTPRequestHandler):
    def _ответ(self, код, тип, тело, заголовки=None):
        self.send_response(код)
        self.send_header("Content-Type", тип)
        self.send_header("Content-Length", str(len(тело)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (заголовки or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(тело)

    def _json(self, объект, код=200):
        self._ответ(код, "application/json; charset=utf-8", json.dumps(объект, ensure_ascii=False, default=str).encode("utf-8"))

    def _поток_хода(self, д, личный=None):
        """Ход с потоком шагов: по строке JSON на событие (NDJSON). «шаг» — новое событие следа, «обновление» — дополнение уже показанного
        (вызов API: «идёт» → «готово»), «итог» — ответ хода, «ошибка» — сбой. Соединение закрывается после последней строки."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        открыт = [True]

        def отправить(событие):
            if not открыт[0]:
                return
            try:
                self.wfile.write((json.dumps(событие, ensure_ascii=False, default=str) + "\n").encode("utf-8"))
                self.wfile.flush()
            except OSError:                       # страницу закрыли: ход всё равно доводим до конца, чтобы состояние сессии не осталось половинчатым
                открыт[0] = False
        try:
            with замок_сессии(д.get("сессия")):
                итог = ход(д, на_шаг=отправить, личный=личный)
            отправить({"т": "итог", "результат": {k: v for k, v in итог.items() if k != "след"}})   # шаги страница уже получила по ходу
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            отправить({"т": "ошибка", "ошибка": "%s: %s" % (type(e).__name__, e)})

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        путь = urllib.parse.unquote(u.path)               # браузер присылает кириллические адреса в процентной записи
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if путь in ("/", "/index.html"):
                with open(СТРАНИЦА, "rb") as f:
                    return self._ответ(200, "text/html; charset=utf-8", f.read())
            if путь == "/api/ст34":                     # линейка сайта: пороги читаются из текста статьи кодом, число страница не угадывает
                import код_ответ as КО
                ко = КО.КодОтвет(СИСТЕМА)
                рез = {"диапазоны": [{"более": a, "до": b, "пункт": c, "категория": d} for a, b, c, d in ко.диапазоны_близорукости()]}
                try:
                    х = abs(float(q.get("дптр", "").replace(",", ".")))
                    буква, кат, поч = ко.пункт_по_диоптриям(х)
                    рез["результат"] = {"значение": х, "пункт": буква, "категория": кат, "почему": поч}
                except ValueError:
                    pass
                return self._json(рез)
            if путь == "/api/config":
                return self._json({"пресет": Д.ПРЕСЕТ, "роли": {k: list(v) for k, v in Д.РОЛИ.items()}})
            if путь == "/api/модели":
                if q.get("обновить"):
                    обновить_живые(True)
                return self._json(список_моделей())
            if путь == "/api/totals":
                return self._json(К.итоги())
            if путь == "/api/журнал":
                return self._json(К.ЖУРНАЛ[-80:])
            if путь == "/api/статьи":
                return self._json([{"ид": ид, "название": а.название, "пунктов": len(а.пункты)} for ид, а in СИСТЕМА.база.статьи.items()])
            if путь == "/api/статья":
                а = статья_json(q.get("ид", ""))
                return self._json(а if а else {"ошибка": "нет такой статьи"}, 200 if а else 404)
            if путь == "/api/поиск":
                слова = [w for w in q.get("q", "").lower().replace("ё", "е").split() if w]
                найдено = []
                for ид, а in СИСТЕМА.база.статьи.items():
                    текст = (а.название + " " + а.сырой).lower().replace("ё", "е")
                    if слова and all(w in текст for w in слова):
                        найдено.append({"ид": ид, "название": а.название})
                return self._json(найдено[:40])
            if путь == "/api/провайдеры":                 # для экрана «подключить свой API»
                return self._json({"провайдеры": провайдеры_для_ключа()})
            if путь == "/api/пороги":                    # калькуляторы порогов статьи: числа читаются из текста статьи (пороги.py)
                try:
                    спец = ПР.спецификация(СИСТЕМА.база, q.get("ид", ""))
                    рез = {"спецификация": спец}
                    ключи = [п["ключ"] for п in спец["поля"]]
                    if any(к in q for к in ключи):
                        рез["результат"] = ПР.решить(СИСТЕМА.база, q.get("ид", ""), {к: q[к] for к in ключи if к in q})
                    return self._json(рез)
                except ПР.Нельзя as e:
                    return self._json({"ошибка": str(e)}, 404)
                except (ValueError, KeyError) as e:
                    return self._json({"ошибка": "неверное значение: %s" % e}, 400)
            if путь == "/api/умныйпоиск":               # поиск ядром NNL: блоки «здоровье» и «право», без внешних моделей и без состояния сессии
                return self._json(умный_поиск(q.get("q", "")))
            if путь == "/api/наблюдение/сессии":
                return self._json(Н.список_сессий())
            if путь == "/api/наблюдение/сессия":
                с = Н.сессия(q.get("id", ""))
                return self._json(с if с else {"ошибка": "нет такой сессии"}, 200 if с else 404)
            if not путь.startswith("/api/"):              # статика сайта: только файлы рядом с сервером и в архив/ (без выхода из папки)
                части = [ч for ч in путь.strip("/").split("/") if ч]
                безопасно = all(ч not in (".", "..") and not ч.startswith(".") for ч in части)
                if безопасно and части and (len(части) == 1 or части[0] in _СТАТИКА_ПАПКИ):
                    п_файла = os.path.join(КАТАЛОГ, *части)
                    вид = _СТАТИКА.get(os.path.splitext(п_файла)[1].lower())
                    if вид and os.path.isfile(п_файла):
                        with open(п_файла, "rb") as f:
                            тип = вид + ("; charset=utf-8" if вид.startswith("text/") or вид in ("application/javascript", "application/json") else "")
                            return self._ответ(200, тип, f.read())
            self._ответ(404, "text/plain", b"not found")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json({"ошибка": "%s: %s" % (type(e).__name__, e)}, 500)

    def do_POST(self):
        try:
            д = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8") or "{}")
            путь = urllib.parse.unquote(self.path)
            if путь == "/api/ключ/проверка":                # проверка своего ключа без расхода токенов: список моделей провайдера
                try:
                    личный = личный_из_заголовков(self.headers)
                except ValueError as e:
                    return self._json({"ок": False, "ошибка": str(e)}, 400)
                if личный is None:
                    return self._json({"ок": False, "ошибка": "ключ не передан"}, 400)
                рез = К.проверить_ключ(личный[0], личный[2])
                if рез.get("ок"):
                    рез["модели"] = [м for м in рез["модели"] if not _НЕ_ЧАТ.search(м)]
                return self._json(рез)
            if путь in ("/api/turn", "/api/turn_stream"):
                try:
                    личный = личный_из_заголовков(self.headers)
                except ValueError as e:
                    return self._json({"ошибка": str(e)}, 400)
                if путь == "/api/turn_stream":
                    return self._поток_хода(д, личный)
                with замок_сессии(д.get("сессия")):
                    return self._json(ход(д, личный=личный))
            if путь == "/api/событие":
                return self._json({"записано": Н.записать_события(str(д.get("сессия", "")), д.get("события"))})
            if путь == "/api/читатель":
                return self._json(читатель(д))
            self._ответ(404, "text/plain", b"not found")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json({"ошибка": "%s: %s" % (type(e).__name__, e)})

    def log_message(self, формат, *args):
        pass


class Сервер(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    порт = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    хост = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"      # 0.0.0.0 — открыть доступ с телефона по LAN
    if хост not in ("127.0.0.1", "0.0.0.0"): хост = "127.0.0.1"
    адреса = ["http://127.0.0.1:%d" % порт]
    if хост == "0.0.0.0":
        try:
            со_сокета = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            со_сокета.connect(("8.8.8.8", 80)); адреса.append("http://" + со_сокета.getsockname()[0] + ":%d" % порт); со_сокета.close()
        except Exception: адреса.append("http://<LAN-IP>:%d" % порт)
    СИСТЕМА = Д.Система()
    threading.Thread(target=обновить_живые, daemon=True).start()          # живые списки моделей — в фоне, старт не ждёт сети
    print("Сайт «Справка по годности»: " + "  —  ".join(адреса) + "  (Ctrl+C — остановить)", flush=True)
    Сервер((хост, порт), Обработчик).serve_forever()
