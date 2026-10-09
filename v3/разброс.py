# -*- coding: utf-8 -*-
"""Добавка к запуск.py (не замена измерителю): насколько потеря «цепочка минус монолит» зависит от зерна случайности.

Для зёрен 2..5 заново и по отдельности обучаются все пять моделей (разбор, здоровье, право, монолит, монолит_основы)
в сравнение/зерна/s<N>/. Зерно 1 — основные модели из блоки/ и сравнение/. Всё меряется тем же измерителем.
Запуск: python разброс.py [--зёрна 2 3 4 5] [--без-обучения]
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

V3 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):  # консоль Windows/PyCharm: печать стрелок и кириллицы без ошибок
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V3)
import запуск as Z  # noqa: E402

PY = sys.executable


def train(seed, root):
    jobs = [["обучение/обучить_разбор.py", "--зерно", str(seed), "--выход", os.path.join(root, "блоки", "разбор")],
            ["обучение/обучить_область.py", "--область", "здоровье", "--зерно", str(seed), "--выход", os.path.join(root, "блоки", "здоровье")],
            ["обучение/обучить_область.py", "--область", "право", "--зерно", str(seed), "--выход", os.path.join(root, "блоки", "право")],
            ["обучение/обучить_монолит.py", "--вход", "текст", "--зерно", str(seed), "--выход", os.path.join(root, "монолит")],
            ["обучение/обучить_монолит.py", "--вход", "основы", "--зерно", str(seed), "--выход", os.path.join(root, "монолит_основы")]]
    for j in jobs:
        p = subprocess.run([PY] + j, cwd=V3, capture_output=True, text=True, encoding="utf-8",
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if p.returncode != 0:
            raise SystemExit(p.stderr[-2000:])
        print("  зерно %d: %s" % (seed, p.stdout.strip().splitlines()[-1]), flush=True)


def measure(bench, blocks_dir, mono_dir):
    k = Z.Kernel(Z.TYPES, Z.ARCH)
    for n in ("разбор", "здоровье", "право"):
        ok, msg = k.attach(os.path.join(blocks_dir, n))
        if not ok:
            raise SystemExit(msg)
    chain = Z.score(bench, Z.run(k, bench))
    misrouted = sum(chain[d]["ответ_другой_области"] for d in Z.DOM)
    row = {"цепочка": chain, "ошибок_области": misrouted}
    for kind in ("монолит", "монолит_основы"):
        recs, _ = Z.monolith_predict(kind, bench, os.path.join(mono_dir, kind))
        row[kind] = Z.score(bench, recs)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--зёрна", type=int, nargs="*", default=[2, 3, 4, 5])
    ap.add_argument("--без-обучения", action="store_true")
    a = ap.parse_args()
    bench = Z.данные.bench()
    rows = {1: measure(bench, Z.BLOCKS, os.path.join(V3, "сравнение"))}
    for s in a.зёрна:
        root = os.path.join(V3, "сравнение", "зерна", "s%d" % s)
        if not a.без_обучения:
            train(s, root)
        rows[s] = measure(bench, os.path.join(root, "блоки"), root)
    keys = ["здоровье", "право", "всего"]
    table = {}
    for name in ("цепочка", "монолит", "монолит_основы"):
        table[name] = {d: [rows[s][name][d]["доля_верных"] for s in rows] for d in keys}
    loss = {}
    for m in ("монолит", "монолит_основы"):
        loss[m] = {d: [round(100 * (x - y), 2) for x, y in zip(table["цепочка"][d], table[m][d])] for d in keys}
    summary = {name: {d: {"среднее": round(float(np.mean(v)), 4), "ст_откл": round(float(np.std(v, ddof=1)), 4)} for d, v in t.items()}
               for name, t in table.items()}
    lsum = {m: {d: {"среднее_пп": round(float(np.mean(v)), 2), "ст_откл_пп": round(float(np.std(v, ddof=1)), 2),
                    "мин": min(v), "макс": max(v)} for d, v in t.items()} for m, t in loss.items()}
    out = {"зёрна": list(rows), "по_зёрнам": {str(s): rows[s] for s in rows}, "доли": table, "сводка": summary,
           "потеря_пп_цепочка_минус": loss, "сводка_потери": lsum,
           "ошибок_области_по_зёрнам": [rows[s]["ошибок_области"] for s in rows]}
    with open(os.path.join(Z.RES, "разброс.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nзёрна:", list(rows))
    for name, t in table.items():
        print("%-15s" % name, {d: v for d, v in t.items()})
    for m, t in lsum.items():
        print("цепочка минус %s:" % m, t)
    print("ошибок области по зёрнам:", out["ошибок_области_по_зёрнам"])


if __name__ == "__main__":
    main()
