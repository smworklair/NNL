# -*- coding: utf-8 -*-
import json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"
sys.path.insert(0, os.path.join(ROOT, "research"))
import numpy as np
from engine_py import PyEngine
t = time.time(); E = PyEngine(ambig=True); print("загрузка %.1f с, статей %d" % (time.time() - t, E.n))
bench = [json.loads(l) for l in open(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl", encoding="utf-8")]
h = [r for r in bench if r["область"] == "здоровье"]
P = E.probs([r["вопрос"] for r in h])
print("форма вероятностей", np.asarray(P).shape)
arts = [d["article_no"] for d in E.docs]
top = [arts[int(np.argmax(p[:len(arts)]))] for p in P]
print("верно первым ответом: %d/%d = %.4f" % (sum(a == r["ответ"] for a, r in zip(top, h)), len(h), sum(a == r["ответ"] for a, r in zip(top, h)) / len(h)))
print("решения:", E.decide(np.asarray(P[:5])))
