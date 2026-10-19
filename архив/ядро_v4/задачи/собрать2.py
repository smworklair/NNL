# -*- coding: utf-8 -*-
"""Наборы составного генератора v2: train2 (60 000, ru+en, обучающие формулировки) + GSM8K train (как в v1),
dev2, тест_ген2_знакомые (новые задачи, обучающие формулировки), тест_ген2_новые_фразы (только проверочные формулировки).
Старые тест_ген_знакомые / тест_ген_новые (генератор v1) остаются как «чужой генератор». Запуск: python задачи/собрать2.py"""
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import генератор2 as G2
from собрать import write, gsm
import hashlib

def gen(lang, mode, n, seed, seen):
    rnd, rows = random.Random(seed), []
    while len(rows) < n:
        d = G2.make(lang, mode, rnd)
        if d["question"] in seen:
            continue
        seen.add(d["question"])
        rows.append(dict(d, источник="генератор2"))
    return rows

def main():
    seen = set()
    old = set()
    for name in ("тест_ген_знакомые", "тест_ген_новые"):
        old |= {json.loads(l)["question"] for l in open(os.path.join(HERE, "наборы", name + ".jsonl"), encoding="utf-8")}
    seen |= old
    tr = gen("ru", "train", 30000, 11, seen) + gen("en", "train", 30000, 12, seen)
    dv = gen("ru", "train", 500, 13, seen) + gen("en", "train", 500, 14, seen)
    te_k = gen("ru", "train", 500, 15, seen) + gen("en", "train", 500, 16, seen)
    te_n = gen("ru", "test", 500, 17, seen) + gen("en", "test", 500, 18, seen)
    for lang in ("ru", "en"):
        g = sorted(gsm(lang, "train"), key=lambda r: hashlib.md5(r["question"].encode("utf-8")).hexdigest())
        dv += g[:200]
        tr += g[200:]
    random.Random(19).shuffle(tr)
    write("train2", tr)
    write("dev2", dv)
    write("тест_ген2_знакомые", te_k)
    write("тест_ген2_новые_фразы", te_n)

if __name__ == "__main__":
    main()
