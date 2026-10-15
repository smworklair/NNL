# -*- coding: utf-8 -*-
"""Проверка единого вызова на локальном поддельном сервере без сети.

Сервер отдаёт сначала 429 с заголовком повтора, потом 200. Проверяется:
переход на следующую модель пула без ожидания, учёт статистики использования,
наличие схемы в теле запроса, отсутствие ключа в журнале и в тексте ошибки,
передача инструментов и возврат вызовов инструментов, сохранение формата ключа кэша,
цена без таблицы как неполная.
Контрольные пары показывают, что проверки умеют краснеть: маскировка включается
и ключ не найден, маскировка подменяется на пустую и ключ найден; внутренний шаг
инструментов ломается и вызовы пропадают.
Флаги --сломай-tools и --сломай-маскировку ставят поломку до основных проверок,
поэтому основные проверки краснеют и процесс завершается с ненулевым кодом.
Все числа в выводе вычисляются во время запуска.
"""
import hashlib
import http.server
import json
import os
import socketserver
import sys
import threading
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import клиент as К  # noqa: E402

ФЕЙК_ЗНАЧЕНИЕ = "fake-secret-test-7b3a9c2d-x1"
ОКРУЖЕНИЕ_КЛЮЧ = "NNL_ФЕЙК_КЛЮЧ"
СХЕМА = {"type": "object", "properties": {"ответ": {"type": "string"}}, "required": ["ответ"]}
ИНСТРУМЕНТЫ = [{"type": "function", "function": {"name": "получить_погоду", "description": "Погода в городе", "parameters": {"type": "object", "properties": {"город": {"type": "string"}}, "required": ["город"]}}}]

ЗАПРОСЫ = []


class Обработчик(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            тело = json.dumps({"error": "не тот путь"}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(тело)))
            self.end_headers()
            self.wfile.write(тело)
            return
        длина = int(self.headers.get("Content-Length", 0) or 0)
        сырое = self.rfile.read(длина) if длина else b"{}"
        try:
            данные = json.loads(сырое.decode("utf-8"))
        except Exception:  # noqa: BLE001
            данные = {}
        модель = str(данные.get("model") or "")
        авторизация = self.headers.get("Authorization") or ""
        есть_авторизация = bool(авторизация.startswith("Bearer ") and len(авторизация) > 8)
        есть_схема = isinstance(данные.get("response_format"), dict) and isinstance((данные.get("response_format") or {}).get("json_schema"), dict)
        есть_инструменты = isinstance(данные.get("tools"), list) and len(данные.get("tools") or []) > 0
        ЗАПРОСЫ.append({"модель": модель, "есть_авторизация": есть_авторизация, "есть_схема": есть_схема, "есть_инструменты": есть_инструменты})
        if модель == "модель-а":
            тело = json.dumps({"error": {"message": "Rate limit exceeded, try again in 5.0s"}}).encode("utf-8")
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "5")
            self.send_header("Content-Length", str(len(тело)))
            self.end_headers()
            self.wfile.write(тело)
            return
        if модель == "модель-ошибка":
            секрет = авторизация[len("Bearer "):] if авторизация.startswith("Bearer ") else ""
            тело = json.dumps({"error": {"message": "плохой ключ %s" % секрет}}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(тело)))
            self.end_headers()
            self.wfile.write(тело)
            return
        if есть_инструменты:
            ответ = {
                "id": "chatcmpl-фейк-инструменты",
                "object": "chat.completion",
                "created": 1,
                "model": модель,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "получить_погоду", "arguments": "{\"город\": \"Тверь\"}"}}]}, "finish_reason": "tool_calls"}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }
        else:
            ответ = {
                "id": "chatcmpl-фейк",
                "object": "chat.completion",
                "created": 1,
                "model": модель,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "{\"ответ\": \"да\"}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }
        тело = json.dumps(ответ).encode("utf-8")
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


def старый_хеш(провайдер, модель, система, история, схема, температура, макс_токенов, размышление):
    return hashlib.sha256(json.dumps([провайдер, модель, система, история, схема, температура, макс_токенов, размышление],
                                     ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def main():
    сломай_tools = "--сломай-tools" in sys.argv
    сломай_маскировку = "--сломай-маскировку" in sys.argv
    ос_имя = "фейк"
    сервер = Сервер(("127.0.0.1", 0), Обработчик)
    порт = сервер.server_address[1]
    поток = threading.Thread(target=сервер.serve_forever, daemon=True)
    поток.start()
    os.environ[ОКРУЖЕНИЕ_КЛЮЧ] = ФЕЙК_ЗНАЧЕНИЕ
    cfg = {"base_url": "http://127.0.0.1:%d/v1" % порт, "ключ_метка": None, "ключ_env": ОКРУЖЕНИЕ_КЛЮЧ,
           "авторизация": "Bearer", "подключён": True, "документация": "локальный поддельный сервер", "модели": ["модель-а", "модель-б"]}
    К._загрузить_провайдеры()[ос_имя] = cfg
    исходный_инструменты = К._приложить_инструменты
    исходная_маскировка = К._скрыть_ключ
    try:
        if сломай_tools:
            К._приложить_инструменты = lambda тело, tools=None, tool_choice=None: тело
        if сломай_маскировку:
            К._скрыть_ключ = lambda текст, ключ: текст
        К.СЧЁТ.clear()
        К.ЖУРНАЛ.clear()
        ЗАПРОСЫ.clear()
        проверок = 0
        прошло = 0

        def отметить(условие, название):
            nonlocal проверок, прошло
            проверок += 1
            if условие:
                прошло += 1
            print("проверка %d: %s — %s" % (проверок, название, "совпало" if условие else "не совпало"), flush=True)
            return условие

        итог_пула = None
        длительность = 0.0
        try:
            начало = time.time()
            итог_пула = К.спросить(ос_имя, "модель-а|модель-б", "система", [("user", "привет")], схема=СХЕМА, температура=0.0, макс_токенов=50, кэш=False, таймаут=20)
            длительность = time.time() - начало
        except Exception as e:  # noqa: BLE001
            print("вызов пула завершился исключением: %s: %s" % (type(e).__name__, str(e)[:200]), flush=True)
        порядок = [з["модель"] for з in ЗАПРОСЫ]
        отметить(порядок == ["модель-а", "модель-б"], "порядок моделей пула (сначала первая, потом вторая), запросов: %d" % len(порядок))
        отметить(длительность < 4.5, "переключение без ожидания повтора, длительность %.2f секунд при повторе 5 секунд" % длительность)
        отметить(итог_пула is not None and итог_пула.get("данные") == {"ответ": "да"}, "данные структурного ответа разобраны")
        отметить(any(з["есть_схема"] for з in ЗАПРОСЫ), "схема json_schema присутствовала в теле запроса")
        вход = sum((в.get("вход") or 0) for в in К.ЖУРНАЛ if в.get("провайдер") == ос_имя and not в.get("ошибка"))
        выход = sum((в.get("выход") or 0) for в in К.ЖУРНАЛ if в.get("провайдер") == ос_имя and not в.get("ошибка"))
        отметить(вход == 11 and выход == 7, "статистика использования в учёте, вход %d выход %d" % (вход, выход))
        журнал_текст = json.dumps(К.ЖУРНАЛ, ensure_ascii=False)
        отметить(ФЕЙК_ЗНАЧЕНИЕ not in журнал_текст, "значение ключа отсутствует в журнале")

        текст_ошибки = ""
        try:
            К.спросить(ос_имя, "модель-ошибка", "система", [("user", "привет")], кэш=False, таймаут=20)
        except К.Ошибка as e:
            текст_ошибки = str(e)
        отметить(ФЕЙК_ЗНАЧЕНИЕ not in текст_ошибки and "<ключ>" in текст_ошибки, "текст ошибки без значения ключа, метка на месте (маскировка включена)")

        ЗАПРОСЫ.clear()
        итог_инструменты = None
        try:
            итог_инструменты = К.спросить(ос_имя, "модель-б", "система", [("user", "погода?")], температура=0.0, макс_токенов=50, кэш=False, таймаут=20, tools=ИНСТРУМЕНТЫ)
        except Exception as e:  # noqa: BLE001
            print("вызов с инструментами завершился исключением: %s" % type(e).__name__, flush=True)
        отметить(any(з["есть_инструменты"] for з in ЗАПРОСЫ), "инструменты присутствовали в теле запроса")
        вызовы = (итог_инструменты or {}).get("tool_calls")
        отметить(isinstance(вызовы, list) and вызовы and вызовы[0].get("function", {}).get("name") == "получить_погоду", "вызовы инструментов возвращены из ответа")

        проба_хеш = старый_хеш("groq", "openai/gpt-oss-120b", "с", [("user", "п")], None, 0.2, 1500, False)
        новый_хеш = К._хеш_запроса("groq", "openai/gpt-oss-120b", "с", [("user", "п")], None, 0.2, 1500, False)
        отметить(проба_хеш == новый_хеш, "формат ключа кэша сохранён для запросов без инструментов")

        цена_неизвестна = К.цена(" groq-модель ", 100, 100) is None
        строка_нд = К.цена_строкой(None, False) == "н/д"
        флаг_счёта = К.СЧЁТ.get(ос_имя, {}).get("usd_неполная") is True
        отметить(цена_неизвестна and строка_нд and флаг_счёта, "цена без таблицы как неполная, строка н/д, флаг в учёте")

        if not сломай_tools and not сломай_маскировку:
            исходная = К._скрыть_ключ
            утечка_найдена = False
            try:
                К._скрыть_ключ = lambda текст, ключ: текст
                try:
                    К.спросить(ос_имя, "модель-ошибка", "система", [("user", "привет")], кэш=False, таймаут=20)
                    текст_сломан = ""
                except К.Ошибка as e:
                    текст_сломан = str(e)
                утечка_найдена = ФЕЙК_ЗНАЧЕНИЕ in текст_сломан
            finally:
                К._скрыть_ключ = исходная
            отметить(утечка_найдена, "покраснение при отключённой маскировке, утечка обнаружена")

            исходный_шаг = К._приложить_инструменты
            сбой_найден = False
            try:
                К._приложить_инструменты = lambda тело, tools=None, tool_choice=None: тело
                ЗАПРОСЫ.clear()
                try:
                    сломанный_итог = К.спросить(ос_имя, "модель-б", "система", [("user", "погода?")], температура=0.0, макс_токенов=50, кэш=False, таймаут=20, tools=ИНСТРУМЕНТЫ)
                except Exception:  # noqa: BLE001
                    сломанный_итог = {}
                сбой_найден = not (isinstance((сломанный_итог or {}).get("tool_calls"), list) and (сломанный_итог or {}).get("tool_calls"))
            finally:
                К._приложить_инструменты = исходный_шаг
            отметить(сбой_найден, "покраснение при сломанном внутреннем шаге инструментов, сбой обнаружен")

        print("проверок: %d, прошло: %d" % (проверок, прошло), flush=True)
        if прошло != проверок:
            sys.exit(1)
    finally:
        К._приложить_инструменты = исходный_инструменты
        К._скрыть_ключ = исходная_маскировка
        try:
            сервер.shutdown()
            сервер.server_close()
        except Exception:  # noqa: BLE001
            pass
        try:
            К._загрузить_провайдеры().pop(ос_имя, None)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
