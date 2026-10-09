# -*- coding: utf-8 -*-
"""Ответы систем v4 на общем тесте (только чтение): блоки знаний v4 напрямую и цепочка v3 на ядре v4."""
import json
import os
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
V4 = r"C:\ЯДРО-ОПЫТ\v4"
sys.path.insert(0, V4)
from ядро import NOT_KNOWN, Kernel  # noqa: E402

OUT = sys.argv[1]
bench = [json.loads(l) for l in open(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl", encoding="utf-8") if l.strip()]

k4 = Kernel(os.path.join(V4, "типы"), os.path.join(V4, "архитектуры"))
for b in ("здоровье", "право"):
    ok, msg = k4.attach(os.path.join(V4, "блоки", b))
    assert ok, (b, msg)
k3 = Kernel(os.path.join(V4, "типы"), os.path.join(V4, "архитектуры"))
for b in ("разбор", "здоровье", "право"):
    ok, msg = k3.attach(os.path.join(V4, "блоки_v3", b))
    assert ok, (b, msg)

res = {"v4_знание": [], "v3_цепочка": []}
for r in bench:
    blk = k4.blocks[r["область"]]
    out = blk.arch.run(blk.obj, r["вопрос"])
    res["v4_знание"].append(str(out.get("id")))
    a, _ = k3.ask(r["вопрос"])
    res["v3_цепочка"].append(None if a == NOT_KNOWN or a.get("область") != r["область"] else str(a.get("id")))
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
for s, v in res.items():
    print(s, sum(p == r["ответ"] for p, r in zip(v, bench)), "/", len(bench))
