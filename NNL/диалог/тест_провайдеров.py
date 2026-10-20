# -*- coding: utf-8 -*-
"""Тест реестра провайдеров: конфиги корректны, заголовки ключа собираются правильно, проверка ключа и ход модели идут через
поддельный локальный сервер (настоящие ключи и сеть не нужны), ключ не попадает в ответы и ошибки."""
import json
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import клиент as К  # noqa: E402

ошибок = 0


def проверка(имя, условие, подробность=""):
    global ошибок
    print(("  ок   " if условие else "  ОШИБКА ") + имя + ((" — " + подробность) if подробность and not условие else ""))
    if not условие:
        ошибок += 1


ЗАПРОСЫ = []


class Поддельный(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _ответ(self, код, тело):
        данные = json.dumps(тело).encode("utf-8")
        self.send_response(код)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(данные)))
        self.end_headers()
        self.wfile.write(данные)

    def do_GET(self):
        ЗАПРОСЫ.append(("GET", self.path, dict(self.headers)))
        if self.headers.get("Authorization") != "Bearer sk-test-KEY-123":
            return self._ответ(401, {"error": "нет"})
        self._ответ(200, {"data": [{"id": "модель-а"}, {"id": "модель-б"}, {"id": "text-embedding-3-small"}]})

    def do_POST(self):
        длина = int(self.headers.get("Content-Length", 0))
        тело = json.loads(self.rfile.read(длина) or b"{}")
        ЗАПРОСЫ.append(("POST", self.path, dict(self.headers), тело))
        if self.headers.get("Authorization") != "Bearer sk-test-KEY-123":
            return self._ответ(401, {"error": {"message": "неверный ключ sk-test-KEY-123"}})
        self._ответ(200, {"choices": [{"message": {"role": "assistant", "content": "привет от модели"}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 5, "completion_tokens": 3}})


сервер = ThreadingHTTPServer(("127.0.0.1", 0), Поддельный)
порт = сервер.server_address[1]
threading.Thread(target=сервер.serve_forever, daemon=True).start()

print("реестр провайдеров")
пр = К._загрузить_провайдеры()
НОВЫЕ = ["openai", "anthropic", "xai", "deepseek", "mistral", "openrouter", "together", "cerebras", "fireworks", "moonshot"]
проверка("все десять новых провайдеров на месте", all(п in пр for п in НОВЫЕ), str([п for п in НОВЫЕ if п not in пр]))
проверка("у каждого https и авторизация", all(str(пр[п]["base_url"]).startswith("https://") and пр[п]["авторизация"] for п in НОВЫЕ))
проверка("имена переменных среды не повторяются", len({пр[п]["ключ_env"] for п in пр if пр[п].get("ключ_env")}) == len([1 for п in пр if пр[п].get("ключ_env")]))
проверка("для своего ключа подходят все новые (подключён не false)", all(пр[п].get("подключён") is not False for п in НОВЫЕ))
проверка("выдуманных имён моделей нет: списки пустые, берутся у провайдера", all(not пр[п]["модели"] for п in НОВЫЕ if п != "mistral"))
проверка("прежние провайдеры не тронуты", all(п in пр for п in ("groq", "gemini", "alibaba", "ollama")))

print("заголовки ключа")
h = К.заголовки_ключа(пр["openai"], "k1abc")
проверка("обычный провайдер: только Bearer", h == {"Authorization": "Bearer k1abc"}, str(h))
h = К.заголовки_ключа(пр["anthropic"], "k2abc")
проверка("Claude: Bearer, x-api-key и anthropic-version", h.get("Authorization") == "Bearer k2abc" and h.get("x-api-key") == "k2abc" and h.get("anthropic-version") == "2023-06-01", str(h))

print("проверка ключа через поддельный сервер")
for имя in ("openai", "anthropic", "xai", "deepseek"):
    cfg0 = dict(пр[имя])
    пр[имя]["base_url"] = "http://127.0.0.1:%d/v1" % порт
    ЗАПРОСЫ.clear()
    р = К.проверить_ключ(имя, "sk-test-KEY-123")
    проверка(имя + ": верный ключ принят, модели получены", р.get("ок") is True and р.get("модели") == ["text-embedding-3-small", "модель-а", "модель-б"], str(р))
    if имя == "anthropic":
        заг = {к.lower(): з for к, з in ЗАПРОСЫ[0][2].items()} if ЗАПРОСЫ else {}
        проверка("Claude: на запрос моделей ушли x-api-key и anthropic-version", заг.get("x-api-key") == "sk-test-KEY-123" and заг.get("anthropic-version") == "2023-06-01", str(заг))
    р2 = К.проверить_ключ(имя, "sk-wrong-KEY")
    проверка(имя + ": неверный ключ отклонён без утечки", р2.get("ок") is False and "sk-wrong-KEY" not in json.dumps(р2, ensure_ascii=False), str(р2))
    пр[имя].clear(); пр[имя].update(cfg0)

print("ход модели с личным ключом через поддельный сервер")
пр["xai"]["base_url"] = "http://127.0.0.1:%d/v1" % порт
ЗАПРОСЫ.clear()
with К.личный_ключ("xai", "sk-test-KEY-123"):
    try:
        ответ = К.спросить("xai", "любая-модель", "Ты помощник.", [{"role": "user", "content": "привет"}])
    except Exception as e:  # noqa: BLE001
        ответ = "ИСКЛЮЧЕНИЕ: %s" % type(e).__name__ + str(e)[:80]
текст = ответ if isinstance(ответ, str) else json.dumps(ответ, ensure_ascii=False)
проверка("ответ получен", "привет от модели" in текст, текст[:120])
пост = [з for з in ЗАПРОСЫ if з[0] == "POST"]
проверка("запрос ушёл на /v1/chat/completions с ключом человека", bool(пост) and пост[0][1].endswith("/chat/completions") and пост[0][2].get("Authorization") == "Bearer sk-test-KEY-123")
with К.личный_ключ("xai", "sk-foreign-KEY"):
    try:
        К.спросить("xai", "любая-модель", "", [{"role": "user", "content": "привет"}])
        утечка = False
    except Exception as e:  # noqa: BLE001
        утечка = "sk-foreign-KEY" in str(e)
проверка("ключ не попадает в текст ошибки", not утечка)

сервер.shutdown()
print("\nОШИБОК: %d" % ошибок)
sys.exit(1 if ошибок else 0)
