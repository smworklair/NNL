# -*- coding: utf-8 -*-
"""Собирает папку dist/ для деплоя Python-ядра NNL как функции Vercel. Всё берётся из репозитория, ничего вручную копировать не нужно.

Запуск:   python военкомат/ядро_api/собрать.py
Деплой:   cd военкомат/ядро_api/dist && vercel deploy --prod --yes --name spravka-godnost --scope smworklairs-projects
Проверка: python военкомат/ядро_api/собрать.py --проверить   (поднимает собранную функцию локально и спрашивает каталог статей и умный поиск)

Что получается: dist/api/index.py (обработчик сервера), dist/core/ (урезанная копия репозитория с теми же путями: NNL, система, внешние),
dist/requirements.txt (numpy), dist/vercel.json, dist/public/ (заглушка: статика здесь не нужна, сайт живёт в военкомат/app).
Ядро в репозитории не меняется: путь к lex_topics.json уже относительный (внешние/lex_topics.json)."""
import os
import shutil
import sys

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
# Откуда брать ядро: в монорепозитории это корень над папкой военкомат, в отдельном репозитории voenkomat укажите путь к клону NNL: NNL_ROOT=...
КОРЕНЬ = os.environ.get("NNL_ROOT") or os.path.dirname(os.path.dirname(ЗДЕСЬ))
DIST = os.path.join(ЗДЕСЬ, "dist")
CORE = os.path.join(DIST, "core")


def копировать(отн, имена=None, шаблон=None, пропуск=()):
    """Копирует файлы из папки отн (путь от корня репозитория) в core/ с тем же путём."""
    ист = os.path.join(КОРЕНЬ, отн)
    if not os.path.isdir(ист):
        raise SystemExit("нет папки в репозитории: " + отн)
    цель = os.path.join(CORE, отн)
    os.makedirs(цель, exist_ok=True)
    for имя in sorted(os.listdir(ист)):
        п = os.path.join(ист, имя)
        if not os.path.isfile(п) or имя in пропуск:
            continue
        if имена is not None and имя not in имена and not (шаблон and имя.endswith(шаблон)):
            continue
        shutil.copy2(п, os.path.join(цель, имя))


def дерево(отн):
    ист = os.path.join(КОРЕНЬ, отн)
    if not os.path.isdir(ист):
        raise SystemExit("нет папки в репозитории: " + отн)
    shutil.copytree(ист, os.path.join(CORE, отн), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"), dirs_exist_ok=True)


def собрать():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, "api"))
    os.makedirs(os.path.join(DIST, "public"))
    # ядро и диалог: только рабочий код и данные, без снимков «до_», стендов и тестов
    копировать("NNL", шаблон=".py")
    for п in ("NNL/каскады",):
        if os.path.isdir(os.path.join(КОРЕНЬ, п)):
            дерево(п)
    ди = os.path.join(КОРЕНЬ, "NNL", "диалог")
    цель = os.path.join(CORE, "NNL", "диалог")
    os.makedirs(цель, exist_ok=True)
    for имя in sorted(os.listdir(ди)):
        п = os.path.join(ди, имя)
        if not os.path.isfile(п) or not имя.endswith((".py", ".json")):
            continue
        if "_до_" in имя or имя.startswith(("тест_", "прогон_", "замер_")) and имя != "тест_порогов.py":
            continue
        shutil.copy2(п, os.path.join(цель, имя))
    # система: язык, архитектуры, служебный код и два боевых блока
    дерево("система/язык")
    дерево("система/архитектуры")
    копировать("система/замер", шаблон=".py")
    if os.path.isdir(os.path.join(КОРЕНЬ, "система", "ядро")):
        дерево("система/ядро")
    for блок in ("здоровье", "право"):
        дерево("система/блоки/основная_внешние.з1/" + блок)
    # внешние данные, которые читает знания.py
    копировать("внешние/документы/pp565", {"статьи_2026.json", "разделы.json", "нет_в_нашей_базе.json"})
    копировать("внешние", {"справочник.json", "lex_topics.json"})

    shutil.copy2(os.path.join(ЗДЕСЬ, "index.py"), os.path.join(DIST, "api", "index.py"))
    shutil.copy2(os.path.join(ЗДЕСЬ, "vercel.json"), os.path.join(DIST, "vercel.json"))
    shutil.copy2(os.path.join(ЗДЕСЬ, "requirements.txt"), os.path.join(DIST, "requirements.txt"))
    with open(os.path.join(DIST, "public", "index.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset=utf-8><title>NNL API</title><p>Ядро NNL. Приложение: spravka-app.vercel.app</p>")
    байт = sum(os.path.getsize(os.path.join(к, ф)) for к, _, фс in os.walk(DIST) for ф in фс)
    print("собрано: %s (%.1f МБ)" % (DIST, байт / 1e6))


def проверить():
    import importlib.util
    import threading
    import time
    import urllib.parse
    import urllib.request
    from http.server import ThreadingHTTPServer
    спек = importlib.util.spec_from_file_location("idx", os.path.join(DIST, "api", "index.py"))
    м = importlib.util.module_from_spec(спек)
    спек.loader.exec_module(м)
    сервер = ThreadingHTTPServer(("127.0.0.1", 8199), м.handler)
    threading.Thread(target=сервер.serve_forever, daemon=True).start()
    time.sleep(0.5)
    q = urllib.parse.quote
    ошибок = 0
    for путь, ждём in (("/api/" + q("статьи"), 88), ("/api/" + q("умныйпоиск") + "?q=" + q("давление 160 на 100"), "43")):
        тело = urllib.request.urlopen("http://127.0.0.1:8199" + путь, timeout=60).read().decode("utf-8")
        ок = (len(__import__("json").loads(тело)) == ждём) if isinstance(ждём, int) else (ждём in тело)
        print(("ок    " if ок else "ОШИБКА"), путь[:40])
        ошибок += 0 if ок else 1
    print("ОШИБОК: %d" % ошибок)
    сервер.shutdown()
    return ошибок


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    собрать()
    if "--проверить" in sys.argv:
        raise SystemExit(1 if проверить() else 0)
