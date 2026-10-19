# -*- coding: utf-8 -*-
"""Собирает все карточки из данные/*.json в один файл макеты_военкомат/карточки_статей.js (window.КАРТОЧКИ_СТАТЕЙ). Сначала проверяет.
Запуск: python собрать.py"""
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
ДАННЫЕ = os.path.join(ЗДЕСЬ, "данные")
ВЫХОД = os.path.join(os.path.dirname(ЗДЕСЬ), "макеты", "карточки_статей.js")

if __name__ == "__main__":
    код = subprocess.call([sys.executable, "-X", "utf8", os.path.join(ЗДЕСЬ, "проверить.py")])
    if код:
        print("Сборка остановлена: сначала исправьте ошибки.")
        sys.exit(1)
    все = {}
    for ф in sorted(os.listdir(ДАННЫЕ), key=lambda x: int(x[:-5]) if x[:-5].isdigit() else 0):
        if ф.endswith(".json"):
            д = json.load(open(os.path.join(ДАННЫЕ, ф), encoding="utf-8"))
            if д.get("блоки"):
                все[ф[:-5]] = д
    шапка = ("/* Карточки статей: чеклист подтверждения, ползунки по порогам, признаки поражения. Файл собирает карточки/собрать.py из карточки/данные/*.json.\n"
             "   Каждая строка опирается на дословную цитату из текста статьи (проверяет карточки/проверить.py). Статус «черновик» значит: врач не проверял. */\n")
    open(ВЫХОД, "w", encoding="utf-8").write(шапка + "window.КАРТОЧКИ_СТАТЕЙ = " + json.dumps(все, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print("собрано карточек: %d → %s" % (len(все), ВЫХОД))
