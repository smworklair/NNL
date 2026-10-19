# -*- coding: utf-8 -*-
"""Печатает компактный текст статей Расписания для составления карточек: название, пункты и примечания (без служебных строк о редакциях).
Запуск: python выгрузить.py 43 44 45     или     python выгрузить.py 1-8"""
import os
import sys

sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ЗДЕСЬ))
import знания as З  # noqa: E402


def список(арг):
    out = []
    for а in арг:
        if "-" in а:
            x, y = а.split("-")
            out += [str(i) for i in range(int(x), int(y) + 1)]
        else:
            out.append(а)
    return out


if __name__ == "__main__":
    база = З.База()
    for ид in список(sys.argv[1:]):
        а = база.статьи.get(ид)
        if а is None:
            print("=== нет статьи", ид)
            continue
        print("=== ст. %s · %s" % (ид, а.название))
        for п in а.пункты:
            буква = п.get("буква") if isinstance(п, dict) else getattr(п, "буква", "")
            опис = п.get("описание") if isinstance(п, dict) else getattr(п, "описание", str(п))
            print("  пункт %s) %s" % (буква, опис))
        for л in а.примечания:
            if л.startswith("Открыть полный текст документа"):
                break                      # дальше идёт мусор с сайта-источника (меню, контакты)
            if л.startswith("(см. текст") or л.startswith("(в ред.") or л.startswith("(абзац введен") or л.startswith("(п. ") or л.startswith("(пункт"):
                continue
            print("  · " + л)
        print()
