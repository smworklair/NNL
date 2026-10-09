# -*- coding: utf-8 -*-
"""Ответы систем v6 на общем тесте (только чтение): TINY 1.6 (сеть приложения напрямую) и NNL Д (ядро v6)."""
import json
import os
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
V6 = r"C:\ЯДРО-ОПЫТ\v6"
sys.path.insert(0, V6)
from ядро import NOT_KNOWN, Kernel  # noqa: E402

OUT = sys.argv[1]
bench = [json.loads(l) for l in open(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl", encoding="utf-8") if l.strip()]

ka = Kernel(os.path.join(V6, "типы"), os.path.join(V6, "архитектуры"))
ok, msg = ka.attach(os.path.join(V6, "блоки", "здоровье.прил3"))
assert ok, msg
app = ka.blocks["здоровье.прил3"]
kd = Kernel(os.path.join(V6, "типы"), os.path.join(V6, "архитектуры"))
for b in ("здоровье.заявка5", "здоровье.прил4", "право.заявка4", "право.знание3"):
    ok, msg = kd.attach(os.path.join(V6, "блоки", b))
    assert ok, (b, msg)

res = {"TINY_1.6": [], "NNL_Д": []}
for r in bench:
    if r["область"] == "здоровье":
        res["TINY_1.6"].append(str(app.arch.run(app.obj, {"область": "здоровье", "текст": r["вопрос"]})["id"]))
    else:
        res["TINY_1.6"].append(None)
    a, _ = kd.ask(r["вопрос"])
    res["NNL_Д"].append(None if a == NOT_KNOWN or a.get("область") != r["область"] else str(a.get("id")))
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
for s, v in res.items():
    print(s, sum(p == r["ответ"] for p, r in zip(v, bench)), "/", len(bench))
