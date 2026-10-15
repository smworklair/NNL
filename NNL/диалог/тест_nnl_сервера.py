# -*- coding: utf-8 -*-
"""Проверка сервера без состояния на поддельном внешнем сервере.

Поддельный внешний сервер отдаёт разбор и речь детерминированно.
Проверяется: список моделей, ответ ядра и базы, детерминизм пересчёта,
база без вызовов ядра, обрыв истории не ломает сервер, потоковая передача
отклоняется понятно, лишние поля игнорируются.
Флаги --сломай-детерминизм, --сломай-базу, --сломай-обрыв ставят поломку
до основных проверок, поэтому соответствующие проверки краснеют.
Все числа вычисляются при запуске.
"""
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.error
import urllib.request

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import клиент as К  # noqa: E402
import nnl_сервер as Н  # noqa: E402
import расследование as Р  # noqa: E402

ФЕЙК_ЗНАЧЕНИЕ = "fake-secret-nnl-9c4a"
ОКРУЖЕНИЕ_КЛЮЧ = "NNL_ФЕЙК_ВНЕШ"
ЗАПРОСЫ_ВНЕШ = []


class Внешний(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        длина = int(self.headers.get("Content-Length", 0) or 0)
        сырое = self.rfile.read(длина) if длина else b"{}"
        try:
            данные = json.loads(сырое.decode("utf-8"))
        except Exception:  # noqa: BLE001
            данные = {}
        формат = данные.get("response_format") or {}
        схема = (формат.get("json_schema") or {}).get("schema") or {}
        свойства = (схема.get("properties") or {})
        ЗАПРОСЫ_ВНЕШ.append({"схема": list(свойства.keys())})
        if "упоминания" in свойства:
            содержание = json.dumps({"упоминания": [{"термин": "тест-жалоба", "статус": "есть", "уточнение": "", "кто_подтвердил": "нет_данных"}], "ответ_на_вопрос": "нет_вопроса", "значение": "", "хочет_завершить": False}, ensure_ascii=False)
        elif "вопросы" in свойства:
            содержание = json.dumps({"реакция": "понял", "вопросы": []}, ensure_ascii=False)
        else:
            содержание = "Понял, расскажите подробнее."
        ответ = {"id": "chatcmpl-фейк", "object": "chat.completion", "created": 1, "model": str(данные.get("model") or ""),
                 "choices": [{"index": 0, "message": {"role": "assistant", "content": содержание}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}}
        тело = json.dumps(ответ, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(тело)))
        self.end_headers()
        self.wfile.write(тело)

    def log_message(self, формат, *args):
        pass


class Сервер(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def пост(порт, объект):
    тело = json.dumps(объект, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:%d/v1/chat/completions" % порт, data=тело, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        try:
            if isinstance(e, urllib.error.HTTPError):
                return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return 0, {"error": "%s" % type(e).__name__}


def гет_модели(порт):
    with urllib.request.urlopen("http://127.0.0.1:%d/v1/models" % порт, timeout=20) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def main():
    сломай_дет = "--сломай-детерминизм" in sys.argv
    сломай_базу = "--сломай-базу" in sys.argv
    сломай_обрыв = "--сломай-обрыв" in sys.argv
    внешний = Сервер(("127.0.0.1", 0), Внешний)
    порт_внеш = внешний.server_address[1]
    threading.Thread(target=внешний.serve_forever, daemon=True).start()
    os.environ[ОКРУЖЕНИЕ_КЛЮЧ] = ФЕЙК_ЗНАЧЕНИЕ
    имя_внеш = "фейк-внеш"
    К._загрузить_провайдеры()[имя_внеш] = {"base_url": "http://127.0.0.1:%d/v1" % порт_внеш, "ключ_метка": None, "ключ_env": ОКРУЖЕНИЕ_КЛЮЧ,
                                            "авторизация": "Bearer", "подключён": True, "документация": "поддельный", "модели": ["модель-б"]}
    import диалог as Д
    Н.СИСТЕМА = Д.Система()
    Н.ВНЕШНЯЯ = (имя_внеш, "модель-б")
    nnl = Сервер(("127.0.0.1", 0), Н.Обработчик)
    порт = nnl.server_address[1]
    threading.Thread(target=nnl.serve_forever, daemon=True).start()
    исходный_ядро = Н.ответить_ядро
    исходная_база = Н.ответить_база
    исходный_польз = Н._пользовательские
    try:
        if сломай_дет:
            import uuid
            def с_шумом(*a, **kw):
                текст, вх, вых, тел = исходный_ядро(*a, **kw)
                return текст + " " + uuid.uuid4().hex[:6], вх, вых, dict(тел, рейтинг=[])
            Н.ответить_ядро = с_шумом
        if сломай_базу:
            def база_с_ядром(сообщения, температура, макс_токенов):
                from диалог import Система
                с = Н.СИСТЕМА.сессия()
                с.ср.учесть_упоминание("тест", "есть", "", {}, 0.5)
                return исходная_база(сообщения, температура, макс_токенов)
            Н.ответить_база = база_с_ядром
        if сломай_обрыв:
            def строгий(сообщения):
                if len(сообщения or []) < 3:
                    raise RuntimeError("обрыв не перенесён")
                return исходный_польз(сообщения)
            Н._пользовательские = строгий
        проверок = 0
        прошло = 0

        def отметить(условие, название):
            nonlocal проверок, прошло
            проверок += 1
            if условие:
                прошло += 1
            print("проверка %d: %s — %s" % (проверок, название, "совпало" if условие else "не совпало"), flush=True)
            return условие

        код, модели = гет_модели(порт)
        ид = sorted(x.get("id") for x in (модели.get("data") or []))
        отметить(код == 200 and ид == ["nnl-база", "nnl-ядро"], "список моделей содержит оба имени, записей: %d" % len(ид))

        диалог_один = [{"role": "user", "content": "Мне 18, болит спина и падает зрение, очки минус шесть. Возьмут в армию?"}]
        код_я, отв_я = пост(порт, {"model": "nnl-ядро", "messages": диалог_один})
        отметить(код_я == 200 and "choices" in отв_я and (отв_я.get("nnl") or {}).get("режим") == "ядро", "ядро отвечает в формате OpenAI с телеметрией")
        код_б, отв_б = пост(порт, {"model": "nnl-база", "messages": диалог_один})
        отметить(код_б == 200 and (отв_б.get("nnl") or {}).get("режим") == "база", "база отвечает без ядра")

        код_я2, отв_я2 = пост(порт, {"model": "nnl-ядро", "messages": диалог_один})
        один_текст = ((отв_я.get("choices") or [{}])[0].get("message") or {}).get("content")
        два_текст = ((отв_я2.get("choices") or [{}])[0].get("message") or {}).get("content")
        один_рейт = (отв_я.get("nnl") or {}).get("рейтинг")
        два_рейт = (отв_я2.get("nnl") or {}).get("рейтинг")
        отметить(код_я2 == 200 and один_текст == два_текст and один_рейт == два_рейт, "повтор диалога даёт то же состояние")

        счёт = {"число": 0}
        исходный_метод = Р.Расследование.учесть_упоминание

        def считающий(self, *a, **kw):
            счёт["число"] += 1
            return исходный_метод(self, *a, **kw)

        Р.Расследование.учесть_упоминание = считающий
        try:
            счёт["число"] = 0
            пост(порт, {"model": "nnl-база", "messages": диалог_один})
            база_число = счёт["число"]
            счёт["число"] = 0
            пост(порт, {"model": "nnl-ядро", "messages": диалог_один})
            ядро_число = счёт["число"]
        finally:
            Р.Расследование.учесть_упоминание = исходный_метод
        отметить(база_число == 0 and ядро_число > 0, "база без ядра %d, ядро %d" % (база_число, ядро_число))

        код_об, отв_об = пост(порт, {"model": "nnl-ядро", "messages": [{"role": "user", "content": "Итог?"}]})
        отметить(код_об == 200 and "choices" in отв_об, "обрыв истории не ломает сервер")

        код_поток, отв_поток = пост(порт, {"model": "nnl-ядро", "messages": диалог_один, "stream": True})
        отметить(код_поток == 400 and "поток" in str(отв_поток.get("error", "")).lower(), "поток отклоняется понятно")

        код_лиш, отв_лиш = пост(порт, {"model": "nnl-база", "messages": диалог_один, "n": 5, "stop": ["x"], "top_p": 0.1})
        отметить(код_лиш == 200 and "choices" in отв_лиш, "лишние поля игнорируются")

        print("проверок: %d, прошло: %d" % (проверок, прошло), flush=True)
        if прошло != проверок:
            sys.exit(1)
    finally:
        Н.ответить_ядро = исходный_ядро
        Н.ответить_база = исходная_база
        Н._пользовательские = исходный_польз
        try:
            внешний.shutdown()
            внешний.server_close()
        except Exception:  # noqa: BLE001
            pass
        try:
            nnl.shutdown()
            nnl.server_close()
        except Exception:  # noqa: BLE001
            pass
        try:
            К._загрузить_провайдеры().pop(имя_внеш, None)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
