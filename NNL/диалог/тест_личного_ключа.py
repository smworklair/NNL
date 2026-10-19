# -*- coding: utf-8 -*-
"""Тест «подключить свой API-ключ» (Помощник α): ключ человека живёт только в одном запросе.
Всё локально: вместо настоящего провайдера — поддельный сервер на 127.0.0.1, настоящие ключи сервера не читаются, журнал и кэш — во временной папке.
Проверяется:
  * ключ уходит провайдеру ровно в том запросе, где человек его передал, и серверный ключ при этом не используется;
  * ключа нет ни в ответах сервера, ни в журнале хода, ни в кэше моделей, ни в тексте ошибок;
  * ответы по чужому ключу не кэшируются (повтор делает новый вызов);
  * после запроса со своим ключом следующий запрос той же сессии без ключа идёт уже с серверным;
  * режим «свободно» (пул потоков) тоже несёт ключ в потоки;
  * неверные заголовки (провайдер, ключ с пробелом, странное имя модели) отклоняются.
Запуск: python NNL/диалог/тест_личного_ключа.py   — без сети и без настоящих моделей."""
import http.server
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ВРЕМЕННАЯ = tempfile.mkdtemp(prefix="nnl_тест_ключа_")
ЛИЧНЫЙ = "TESTKEY-abcdef123456"
СЕРВЕРНЫЙ = "SERVERKEY-999999999"

import клиент as К  # noqa: E402
К.КЭШ_ФАЙЛ = os.path.join(ВРЕМЕННАЯ, "кэш_моделей.jsonl")
К._кэш = None
К.ФАЙЛ_КЛЮЧЕЙ = os.path.join(ВРЕМЕННАЯ, "нет_такого_файла.txt")
К._ключи = lambda: {"fake": СЕРВЕРНЫЙ}                      # настоящие ключи сервера не трогаем
import наблюдение as Н  # noqa: E402
Н.КАТАЛОГ = os.path.join(ВРЕМЕННАЯ, "журнал_работы")
import диалог as Д  # noqa: E402
import сервер as S  # noqa: E402

ВИДЕЛ = []     # (путь, значение Authorization) каждого запроса к поддельному провайдеру
ЛОК = threading.Lock()


class Поддельный(http.server.BaseHTTPRequestHandler):
    def _авториз(self):
        return self.headers.get("Authorization")

    def do_GET(self):
        a = self._авториз()
        with ЛОК:
            ВИДЕЛ.append((self.path, a))
        if self.path.endswith("/models"):
            if a != "Bearer " + ЛИЧНЫЙ and a != "Bearer " + СЕРВЕРНЫЙ:
                self.send_response(401); self.end_headers(); self.wfile.write(b'{"error":"bad key"}'); return
            тело = json.dumps({"data": [{"id": "fake-1"}, {"id": "fake-text-embedding"}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(тело); return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); self.rfile.read(n)
        with ЛОК:
            ВИДЕЛ.append((self.path, self._авториз()))
        ответ = {"choices": [{"message": {"content": json.dumps({"ответ": "проверка связи", "главное": "проверка связи", "пояснение": "ok"}, ensure_ascii=False)}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 5, "completion_tokens": 5}}
        тело = json.dumps(ответ, ensure_ascii=False).encode("utf-8")
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(тело))); self.end_headers(); self.wfile.write(тело)

    def log_message(self, *a):
        pass


поддельный = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Поддельный)
threading.Thread(target=поддельный.serve_forever, daemon=True).start()
К._загрузить_провайдеры()["fake"] = {"base_url": "http://127.0.0.1:%d/v1" % поддельный.server_address[1], "авторизация": "Bearer", "подключён": True, "модели": ["fake-1"]}

S.СИСТЕМА = Д.Система()
сервер = S.Сервер(("127.0.0.1", 0), S.Обработчик)
threading.Thread(target=сервер.serve_forever, daemon=True).start()
АДРЕС = "http://127.0.0.1:%d" % сервер.server_address[1]
ошибки = []


def проверить(что, условие, подробность=""):
    print(("  ок   " if условие else "  ОШИБКА ") + что + ("" if условие else "  " + str(подробность)))
    if not условие:
        ошибки.append(что)


def запрос(путь, тело=None, заголовки=None):
    данные = json.dumps(тело or {}, ensure_ascii=False).encode("utf-8") if тело is not None else None
    req = urllib.request.Request(АДРЕС + urllib.parse.quote(путь), data=данные, headers=dict({"Content-Type": "application/json"}, **(заголовки or {})))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


ЛИЧНЫЕ_ЗАГОЛОВКИ = {"X-NNL-Provider": "fake", "X-NNL-Model": "fake-1", "X-NNL-Key": ЛИЧНЫЙ}


def чат_вызовы():
    return [а for п, а in ВИДЕЛ if п.endswith("/chat/completions")]


print("проверка ключа:")
код, тело = запрос("/api/ключ/проверка", {}, ЛИЧНЫЕ_ЗАГОЛОВКИ)
проверить("верный ключ принят", код == 200 and json.loads(тело).get("ок") is True, (код, тело))
проверить("служебные модели отфильтрованы", json.loads(тело).get("модели") == ["fake-1"], тело)
проверить("ключа нет в ответе проверки", ЛИЧНЫЙ not in тело)
код, тело = запрос("/api/ключ/проверка", {}, dict(ЛИЧНЫЕ_ЗАГОЛОВКИ, **{"X-NNL-Key": "WRONGKEY-123456789"}))
проверить("неверный ключ не принят", json.loads(тело).get("ок") is False, тело)
проверить("ключа нет в тексте ошибки", "WRONGKEY" not in тело, тело)

print("ход со своим ключом:")
ВИДЕЛ.clear()
код, тело = запрос("/api/turn", {"сессия": "т1", "режим": "база", "текст": "Что такое категория годности?"}, ЛИЧНЫЕ_ЗАГОЛОВКИ)
проверить("ход выполнен", код == 200 and '"ошибка"' not in тело[:200], (код, тело[:300]))
вызовы = чат_вызовы()
проверить("провайдер получил ЛИЧНЫЙ ключ", вызовы and all(а == "Bearer " + ЛИЧНЫЙ for а in вызовы), вызовы)
проверить("серверный ключ не использовался", not any(а == "Bearer " + СЕРВЕРНЫЙ for а in вызовы), вызовы)
проверить("ключа нет в ответе сервера", ЛИЧНЫЙ not in тело)
n1 = len(вызовы)
запрос("/api/turn", {"сессия": "т1", "режим": "база", "текст": "Что такое категория годности?"}, ЛИЧНЫЕ_ЗАГОЛОВКИ)
проверить("повтор того же вопроса не берётся из кэша", len(чат_вызовы()) > n1, (n1, len(чат_вызовы())))

print("следующий ход без ключа:")
ВИДЕЛ.clear()
роли = {r: ["fake", "fake-1"] for r in S.РОЛИ_ИМЕНА}
код, тело = запрос("/api/turn", {"сессия": "т1", "режим": "база", "текст": "Ещё вопрос", "роли": роли}, {})
вызовы = чат_вызовы()
проверить("без ключа идёт серверный ключ", вызовы and all(а == "Bearer " + СЕРВЕРНЫЙ for а in вызовы), (код, вызовы, тело[:200]))
проверить("личного ключа в вызове нет", not any(ЛИЧНЫЙ in (а or "") for а in вызовы))

print("режим «свободно» (пул потоков):")
ВИДЕЛ.clear()
код, тело = запрос("/api/turn", {"сессия": "т2", "режим": "свободно", "текст": "Первый вопрос про сердце. Второй вопрос про зрение."}, ЛИЧНЫЕ_ЗАГОЛОВКИ)
вызовы = чат_вызовы()
проверить("все вызовы потоков несут личный ключ", вызовы and all(а == "Bearer " + ЛИЧНЫЙ for а in вызовы), (код, вызовы, тело[:200]))

print("где ключа быть не должно:")
найдено = []
for корень, _, файлы in os.walk(ВРЕМЕННАЯ):
    for ф in файлы:
        п = os.path.join(корень, ф)
        try:
            if ЛИЧНЫЙ.encode() in open(п, "rb").read():
                найдено.append(п)
        except OSError:
            pass
проверить("ключа нет ни в журнале, ни в кэше", not найдено, найдено)
проверить("журнал хода записан без ключа", os.path.isdir(Н.КАТАЛОГ) and os.listdir(Н.КАТАЛОГ))
проверить("кэш моделей пуст для этих запросов", not os.path.exists(К.КЭШ_ФАЙЛ) or ЛИЧНЫЙ not in open(К.КЭШ_ФАЙЛ, encoding="utf-8").read())

print("неверные заголовки:")
for имя, з in [("неизвестный провайдер", {"X-NNL-Provider": "no_such_provider", "X-NNL-Model": "m", "X-NNL-Key": ЛИЧНЫЙ}),
               ("ключ с пробелом", dict(ЛИЧНЫЕ_ЗАГОЛОВКИ, **{"X-NNL-Key": "KEY WITH SPACE 123"})),
               ("слишком короткий ключ", dict(ЛИЧНЫЕ_ЗАГОЛОВКИ, **{"X-NNL-Key": "abc"})),
               ("странное имя модели", dict(ЛИЧНЫЕ_ЗАГОЛОВКИ, **{"X-NNL-Model": "m;rm -rf"}))]:
    код, тело = запрос("/api/turn", {"сессия": "т3", "режим": "база", "текст": "тест"}, з)
    проверить(имя + " → 400", код == 400, (код, тело[:120]))
код, тело = запрос("/api/провайдеры")
проверить("список провайдеров отдаётся без ключей", "SERVERKEY" not in тело and "fake" in тело, тело[:200])

сервер.shutdown(); поддельный.shutdown()
print("\nОШИБОК: %d" % len(ошибки))
sys.exit(1 if ошибки else 0)
