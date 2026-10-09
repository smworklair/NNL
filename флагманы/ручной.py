# -*- coding: utf-8 -*-
"""Ручной замер через обычные чаты (ChatGPT, Grok, Claude.ai и другие) — без ключей API и без оплаты по токенам.

1) Выгрузить выборку пачками:
     python -I ручной.py экспорт --выборка 60
   В папке ручной/ появятся пачка_01.txt … пачка_06.txt. Каждая пачка — полный запрос: инструкция, список и 10 вопросов.
2) Для каждой пачки откройте НОВЫЙ чат (чтобы пачки не влияли друг на друга), по возможности без веб-поиска и памяти,
   вставьте текст целиком, ответ модели (JSON) сохраните в файл, например ручной/chatgpt_01.txt, ручной/chatgpt_02.txt …
   Номер в конце имени файла — номер пачки.
3) Загрузить ответы:
     python -I ручной.py импорт --имя chatgpt_веб ручной/chatgpt_*.txt
   Появится ответы/chatgpt_веб.jsonl. В оценке системы сравниваются на тех же вопросах выборки.
Выборка общая для всех чатов (зерно 1), чтобы сравнение было на одних и тех же вопросах."""
import argparse
import glob
import json
import os
import random
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from замер_общее import ОТВЕТЫ, ROOT, write_jl, набор, пачки, разобрать, системный_текст, текст_вопросов  # noqa: E402

ПАПКА = os.path.join(ROOT, "ручной")
ВЫБОРКА = os.path.join(ПАПКА, "выборка.json")


def экспорт(a):
    rows = набор()
    keys = sorted(random.Random(a.зерно).sample(range(len(rows)), a.выборка))
    chosen = [rows[k] for k in keys]
    os.makedirs(ПАПКА, exist_ok=True)
    batches = пачки(chosen, a.пачка)
    json.dump({"зерно": a.зерно, "пачка": a.пачка, "пачки": [[r["ключ"] for r in b] for b in batches]},
              open(ВЫБОРКА, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    system = системный_текст()
    for n, b in enumerate(batches, 1):
        with open(os.path.join(ПАПКА, "пачка_%02d.txt" % n), "w", encoding="utf-8") as f:
            f.write(system + "\n\n" + текст_вопросов(b) + "\n")
    print("выгружено %d пачек по %d вопросов в %s" % (len(batches), a.пачка, ПАПКА))


def импорт(a):
    sel = json.load(open(ВЫБОРКА, encoding="utf-8"))
    files = []
    for p in a.файлы:
        files += glob.glob(p) or [p]
    out, used = [], set()
    for path in sorted(set(files)):
        m = re.search(r"(\d+)\D*$", os.path.basename(path))
        if not m or not 1 <= int(m.group(1)) <= len(sel["пачки"]):
            print("пропущен (нет номера пачки в имени):", path)
            continue
        n = int(m.group(1))
        keys = sel["пачки"][n - 1]
        parsed = разобрать(open(path, encoding="utf-8").read(), len(keys))
        for k, key in enumerate(keys, 1):
            if k in parsed:
                area, idv, conf = parsed[k]
                out.append({"ключ": key, "область": area, "id": idv, "уверенность": conf, "ручной": True})
            else:
                out.append({"ключ": key, "сбой": "нет ответа", "ручной": True})
        used.add(n)
        print("пачка %d: разобрано %d из %d" % (n, len(parsed), len(keys)))
    write_jl(os.path.join(ОТВЕТЫ, a.имя + ".jsonl"), out)
    missing = [n for n in range(1, len(sel["пачки"]) + 1) if n not in used]
    print("записано ответы/%s.jsonl: %d ответов; пачки без файла: %s" % (a.имя, sum("сбой" not in o for o in out), missing or "нет"))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="что", required=True)
    e = sub.add_parser("экспорт")
    e.add_argument("--выборка", type=int, default=60)
    e.add_argument("--пачка", type=int, default=10)
    e.add_argument("--зерно", type=int, default=1)
    i = sub.add_parser("импорт")
    i.add_argument("--имя", required=True)
    i.add_argument("файлы", nargs="+")
    a = p.parse_args()
    экспорт(a) if a.что == "экспорт" else импорт(a)


if __name__ == "__main__":
    main()
