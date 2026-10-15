# -*- coding: utf-8 -*-
"""Сервер NNL в формате OpenAI без состояния.

Конечные точки на адресе 127.0.0.1:
  GET /v1/models — список имён nnl-ядро и nnl-база;
  POST /v1/chat/completions — ответ в формате OpenAI плюс поле nnl с телеметрией.

Имена моделей:
  nnl-ядро — ответ строит наше ядро (расследование.py и диалог.py), состояние
    пересчитывается из истории messages при каждом запросе;
  nnl-база — та же внешняя модель без ядра, прямой вызов через клиент.py.

Какая внешняя модель стоит под обоими именами — параметр запуска --внешняя
вида провайдер:модель, значение в коде не зашито.
Потоковая передача не поддерживается и отвечает понятной ошибкой.
Данные пользователя в журналы не пишутся.
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import диалог as Д  # noqa: E402
import клиент as К  # noqa: E402

ИМЕНА = ("nnl-ядро", "nnl-база")
СИСТЕМА = None
ВНЕШНЯЯ = ("groq", "openai/gpt-oss-120b")
ЗАМОК_РОЛЕЙ = threading.Lock()


def _роль_внешней(текст):
    пров, _, мод = str(текст).partition(":")
    if not пров or not мод:
        raise ValueError("внешняя модель задаётся как провайдер:модель")
    return пров, мод


def _температура(тело):
    try:
        t = float(тело.get("temperature", 0.2))
    except Exception:  # noqa: BLE001
        return 0.2
    return t


def _макс_токенов(тело):
    for ключ in ("max_completion_tokens", "max_tokens"):
        if тело.get(ключ) is not None:
            try:
                return max(1, int(тело.get(ключ)))
            except Exception:  # noqa: BLE001
                pass
    return 800


def _пользовательские(сообщения):
    тексты = []
    for m in сообщения or []:
        if not isinstance(m, dict):
            continue
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str) and c.strip():
            тексты.append(c)
    return тексты


def _для_базы(сообщения):
    система = ""
    история = []
    for m in сообщения or []:
        if not isinstance(m, dict):
            continue
        роль = m.get("role")
        c = m.get("content")
        if isinstance(c, list):
            c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
        if not isinstance(c, str):
            continue
        if роль == "system" and not система and not история:
            система = c
        elif роль == "user":
            история.append(("user", c))
        elif роль == "assistant":
            история.append(("model", c))
        elif роль == "tool":
            история.append(dict(m))
    return система, история


def ответить_ядро(сообщения, температура, макс_токенов):
    пользовательские = _пользовательские(сообщения)
    if not пользовательские:
        raise К.Ошибка("нет сообщений пользователя")
    пров, мод = ВНЕШНЯЯ
    with ЗАМОК_РОЛЕЙ:
        старые = dict(Д.РОЛИ)
        try:
            for роль in list(Д.РОЛИ.keys()):
                Д.РОЛИ[роль] = (пров, мод)
            сессия = СИСТЕМА.сессия()
            начало_журнала = len(К.ЖУРНАЛ)
            последний = None
            for текст in пользовательские:
                последний = сессия.ход(текст)
        finally:
            for роль, значение in старые.items():
                Д.РОЛИ[роль] = значение
    вызовы = К.ЖУРНАЛ[начало_журнала:]
    токены_вход = sum((в.get("вход") or 0) for в in вызовы)
    токены_выход = sum((в.get("выход") or 0) for в in вызовы)
    текст = (последний or {}).get("ответ", "")
    телеметрия = {"режим": "ядро", "действие": (последний or {}).get("действие"), "причина": (последний or {}).get("причина"),
                  "рейтинг": (последний or {}).get("рейтинг", [])[:4], "вызовов_модели": sum(1 for в in вызовы if not в.get("кэш")),
                  "токены": токены_вход + токены_выход}
    return текст, токены_вход, токены_выход, телеметрия


def ответить_база(сообщения, температура, макс_токенов):
    система, история = _для_базы(сообщения)
    if not история:
        raise К.Ошибка("нет сообщений пользователя")
    пров, мод = ВНЕШНЯЯ
    начало = len(К.ЖУРНАЛ)
    r = К.спросить(пров, мод, система, история, температура=температура, макс_токенов=макс_токенов, кэш=False, таймаут=120)
    вызовы = К.ЖУРНАЛ[начало:]
    токены_вход = r.get("токены_вход", 0) or 0
    токены_выход = r.get("токены_выход", 0) or 0
    телеметрия = {"режим": "база", "вызовов_модели": sum(1 for в in вызовы if not в.get("кэш")), "токены": токены_вход + токены_выход}
    return r.get("текст", ""), токены_вход, токены_выход, телеметрия


class Обработчик(http.server.BaseHTTPRequestHandler):
    def _отправить(self, код, объект):
        тело = json.dumps(объект, ensure_ascii=False).encode("utf-8")
        self.send_response(код)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(тело)))
        self.end_headers()
        self.wfile.write(тело)

    def do_GET(self):
        if self.path == "/v1/models":
            return self._отправить(200, {"object": "list", "data": [{"id": "nnl-ядро", "object": "model", "owned_by": "nnl"}, {"id": "nnl-база", "object": "model", "owned_by": "nnl"}]})
        return self._отправить(404, {"error": "неизвестный адрес"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            return self._отправить(404, {"error": "неизвестный адрес"})
        try:
            длина = int(self.headers.get("Content-Length", 0) or 0)
        except Exception:  # noqa: BLE001
            длина = 0
        try:
            тело = json.loads(self.rfile.read(длина).decode("utf-8") if длина else "{}")
        except Exception:  # noqa: BLE001
            return self._отправить(400, {"error": "тело запроса не JSON"})
        try:
            if тело.get("stream"):
                return self._отправить(400, {"error": "потоковая передача не поддерживается, запросите без stream"})
            модель = str(тело.get("model") or "")
            if модель not in ИМЕНА:
                return self._отправить(400, {"error": "неизвестная модель, доступны nnl-ядро и nnl-база"})
            сообщения = тело.get("messages")
            if not isinstance(сообщения, list) or not сообщения:
                return self._отправить(400, {"error": "поле messages должно быть непустым списком"})
            температура = _температура(тело)
            макс_токенов = _макс_токенов(тело)
            if модель == "nnl-ядро":
                текст, т_вх, т_вых, телеметрия = ответить_ядро(сообщения, температура, макс_токенов)
            else:
                текст, т_вх, т_вых, телеметрия = ответить_база(сообщения, температура, макс_токенов)
            ответ = {"id": "chatcmpl-" + uuid.uuid4().hex[:12], "object": "chat.completion", "created": int(time.time()), "model": модель,
                     "choices": [{"index": 0, "message": {"role": "assistant", "content": текст}, "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": т_вх, "completion_tokens": т_вых, "total_tokens": т_вх + т_вых}, "nnl": телеметрия}
            return self._отправить(200, ответ)
        except К.Ошибка as e:
            return self._отправить(200, {"error": "%s" % e})
        except Exception as e:  # noqa: BLE001
            return self._отправить(500, {"error": "%s" % type(e).__name__})

    def log_message(self, формат, *args):
        pass


class Сервер(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    global СИСТЕМА, ВНЕШНЯЯ
    p = argparse.ArgumentParser()
    p.add_argument("--внешняя", default="groq:openai/gpt-oss-120b")
    p.add_argument("--порт", type=int, default=18200)
    p.add_argument("--хост", default="127.0.0.1")
    a = p.parse_args()
    ВНЕШНЯЯ = _роль_внешней(a.внешняя)
    СИСТЕМА = Д.Система()
    print("NNL сервер: http://%s:%d модели nnl-ядро и nnl-база через %s:%s" % (a.хост, a.порт, ВНЕШНЯЯ[0], ВНЕШНЯЯ[1]), flush=True)
    Сервер((a.хост, a.порт), Обработчик).serve_forever()


if __name__ == "__main__":
    main()
