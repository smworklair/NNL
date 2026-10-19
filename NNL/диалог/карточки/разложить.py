# -*- coding: utf-8 -*-
"""Раскладывает пачку карточек (один JSON-файл со словарём {ид: карточка}) по файлам данные/<ид>.json и сразу проверяет их.
В цитатах кавычки пишем как «...»: проверка приводит их к тем же кавычкам, что и в статье.
Запуск: python разложить.py пачки/пачка_01.json"""
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    пачка = json.load(open(sys.argv[1], encoding="utf-8"))
    ид_список = []
    for ид, к in пачка.items():
        к["ид"] = ид
        к.setdefault("статус", "черновик")
        к.setdefault("блоки", [])
        json.dump(к, open(os.path.join(ЗДЕСЬ, "данные", ид + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        ид_список.append(ид)
    sys.exit(subprocess.call([sys.executable, "-X", "utf8", os.path.join(ЗДЕСЬ, "проверить.py")] + ид_список))
