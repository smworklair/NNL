# -*- coding: utf-8 -*-
"""Ряд NNL: системы v6 отвечают на набор замера флагманов. Ядро и блоки v6 — только чтение, след не пишется.

Системы — те, что агенты записали в предсказаниях до замера (без подбора под этот набор):
  В2б — база v6 (заявка здоровья 3, знание здоровья прил4, заявка права 2, знание права 2б);
  Д   — последняя предсказанная система v6 (заявки и знание права на чистой разметке).
«Не знаю» ядра записывается как область «вне» с пустым id. Пишет ответы/nnl_<система>.jsonl.
Запуск: python -I nnl.py"""
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from замер_общее import ОТВЕТЫ, V6, write_jl, набор  # noqa: E402

sys.path.insert(0, V6)
from ядро import NOT_KNOWN, Kernel  # noqa: E402

СИСТЕМЫ = {"В2б": ["здоровье.заявка3", "здоровье.прил4", "право.заявка2", "право.знание2б"],
           "Д": ["здоровье.заявка5", "здоровье.прил4", "право.заявка4", "право.знание3"]}


def main():
    rows = набор()
    for name, blocks in СИСТЕМЫ.items():
        t0 = time.time()
        k = Kernel(os.path.join(V6, "типы"), os.path.join(V6, "архитектуры"))
        for b in blocks:
            ok, msg = k.attach(os.path.join(V6, "блоки", b))
            assert ok, (b, msg)
        out = []
        for r in rows:
            a, rec = k.ask(r["текст"])
            if a == NOT_KNOWN:
                out.append({"ключ": r["ключ"], "область": "вне", "id": "", "уверенность": None, "отказ": rec.get("отказ")})
            else:
                idv = str(a.get("id") or "")
                out.append({"ключ": r["ключ"], "область": a["область"], "id": "" if idv == "∅" else idv,
                            "уверенность": a.get("p")})
        write_jl(os.path.join(ОТВЕТЫ, "nnl_%s.jsonl" % name), out)
        print("NNL %s: %d ответов, %d «не знаю», чисел %d, %.0f с" % (
            name, len(out), sum(o["область"] == "вне" for o in out), k.total_numbers(), time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
