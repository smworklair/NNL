# -*- coding: utf-8 -*-
"""Стенд NNL: диалог, читалка Расписания болезней, бенчмарки и состояние системы. Запуск: python NNL/диалог/сервер.py [порт=8090]

Страница лежит в стенд.html (читается при каждом открытии — правки видны без перезапуска).
Только то, что реально измерено в этом запуске: задержка и токены каждого вызова, число обращений к моделям, вероятности по статьям,
решение ядра и его причина, таблица выбора вопроса, охрана чисел и ссылок. Никаких зашитых цифр точности.

Конечные точки:
  GET  /                      страница
  GET  /api/config            пресеты и роли по умолчанию
  GET  /api/модели            все модели из провайдеры.json (с признаком «ключ есть») и пресеты
  GET  /api/totals            счётчики вызовов по провайдерам
  GET  /api/журнал            последние вызовы моделей (без текста запросов)
  GET  /api/статьи            список статей Расписания;  /api/статья?ид=34 — одна статья;  /api/поиск?q=...
  POST /api/turn              ход диалога  {сессия, режим: nnl|ядро|база, текст, роли?, глубже?}; nnl — только ядро без моделей, ядро — NNL+API, база — только модель
  POST /api/turn_stream       то же, но шаги следа (блоки, ядро, вызовы API с входом, выходом и рассуждением, охрана) приходят по мере работы строками JSON
  POST /api/событие           {сессия, события: [{время, тип, цель, значение}]} — нажатия и выбор на странице в журнал наблюдения
  GET  /api/наблюдение/сессии     сессии из журнала;  /api/наблюдение/сессия?id=...  хронология, проверки и метрики одной сессии
  POST /api/читатель         вопрос к модели по статье с проверкой цитат  {ид, вопрос, модель?, выделено?}
  POST /api/бенч/запуск       {кандидаты, тесты, метка}   GET /api/бенч/статус?id=...   GET /api/бенч/история   GET /api/бенч/прогон?файл=..."""
import http.server
import json
import os
import socketserver
import sys
import re
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import диалог as Д  # noqa: E402
import клиент as К  # noqa: E402
import знания as З  # noqa: E402
import ссылки as С  # noqa: E402
import бенч as Б  # noqa: E402
import наблюдение as Н  # noqa: E402

КАТАЛОГ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
СТРАНИЦА = os.path.join(КАТАЛОГ, "стенды", "стенд.html")
СИСТЕМА = None
СЕССИИ = {}
ЗАМОК = threading.Lock()        # только для бенча: его ходы идут по одному
_ЗАМКИ_СЕССИЙ = {}
_ЗАМОК_ЗАМКОВ = threading.Lock()


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


def ход(д, на_шаг=None):
    """Один ход. на_шаг — функция(событие), куда сразу уходит каждый шаг следа (потоковая страница); без неё след приходит только в ответе."""
    с = получить_сессии(д["сессия"])[д["режим"]]
    р = _роли_из_запроса(д)
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

    def _поток_хода(self, д):
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
                итог = ход(д, на_шаг=отправить)
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
            if путь == "/военкомат.html":
                п_сайта = os.path.join(КАТАЛОГ, "макеты", "военкомат.html")
                if not os.path.exists(п_сайта):
                    п_сайта = os.path.join(КАТАЛОГ, "военкомат.html")
                with open(п_сайта, "rb") as f:
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
            if путь == "/api/бенч/статус":
                с = Б.статус(q.get("id", ""))
                return self._json(с if с else {"ошибка": "нет такой задачи"}, 200 if с else 404)
            if путь == "/api/бенч/история":
                return self._json({"прогоны": Б.история(), "тесты": Б.ТЕСТЫ, "сценарии": [{"id": s["id"], "реплики": s["реплики"], "проверки": s["проверки"]} for s in Б.СЦЕНАРИИ]})
            if путь == "/api/бенч/прогон":
                д = Б.загрузить(q.get("файл", ""))
                return self._json(д if д else {"ошибка": "нет файла"}, 200 if д else 404)
            if путь == "/api/наблюдение/сессии":
                return self._json(Н.список_сессий())
            if путь == "/api/наблюдение/сессия":
                с = Н.сессия(q.get("id", ""))
                return self._json(с if с else {"ошибка": "нет такой сессии"}, 200 if с else 404)
            self._ответ(404, "text/plain", b"not found")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json({"ошибка": "%s: %s" % (type(e).__name__, e)}, 500)

    def do_POST(self):
        try:
            д = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8") or "{}")
            путь = urllib.parse.unquote(self.path)
            if путь == "/api/turn":
                with замок_сессии(д.get("сессия")):
                    return self._json(ход(д))
            if путь == "/api/turn_stream":
                return self._поток_хода(д)
            if путь == "/api/событие":
                return self._json({"записано": Н.записать_события(str(д.get("сессия", "")), д.get("события"))})
            if путь == "/api/читатель":
                return self._json(читатель(д))
            if путь == "/api/бенч/запуск":
                кандидаты = [str(x) for x in д.get("кандидаты", []) if ":" in str(x)]
                тесты = [т for т in д.get("тесты", []) if т in Б.ТЕСТЫ]
                if not кандидаты or not тесты:
                    return self._json({"ошибка": "нужен хотя бы один кандидат и один тест"})
                return self._json({"id": Б.запустить(кандидаты, тесты, str(д.get("метка", ""))[:40], система=СИСТЕМА, замок=ЗАМОК)})
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
    СИСТЕМА = Д.Система()
    threading.Thread(target=обновить_живые, daemon=True).start()          # живые списки моделей — в фоне, старт не ждёт сети
    print("NNL стенд: http://127.0.0.1:%d  (Ctrl+C — остановить)" % порт, flush=True)
    Сервер(("127.0.0.1", порт), Обработчик).serve_forever()
