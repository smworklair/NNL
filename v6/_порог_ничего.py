# -*- coding: utf-8 -*-
"""Подбор порога «∅» знания права по dev (lex dev + 15 % пула), проверочные наборы не читаются."""
import os, random, sys
sys.dont_write_bytecode = True
V6 = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, V6); sys.path.insert(0, os.path.join(V6, "архитектуры"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from обучение import данные, реальные
import общее as G, текст as T, знание as Z
rows, _ = реальные.pool(); rnd = random.Random(1); rnd.shuffle(rows); cut = int(len(rows) * 0.15); p_dev = rows[:cut]
lex = данные.domain_data("право", "dev")
law = [(r["текст"], r["право"]) for r in p_dev if r["право"]]
oth = [r["текст"] for r in p_dev if r["право"] is None]
for name in sys.argv[1:]:
    P = G.load_npz(os.path.join(V6, "блоки", name, "веса.npz")); cls = [str(c) for c in P.pop("классы")]; k = cls.index(Z.NOTHING)
    pr = lambda t: G.forward(P, T.features(t, 1 << 16))
    L = [(pr(t), y) for t, y in lex]; W = [(pr(t), ys) for t, ys in law]; O = [pr(t) for t in oth]
    top = lambda p: cls[int(np.argmax(np.delete(p, k)) + (np.argmax(np.delete(p, k)) >= k))]
    print("==", name, "без ∅: lex %.4f пул-тема %d/%d" % (np.mean([top(p) == y for p, y in L]), sum(top(p) in ys for p, ys in W), len(W)))
    for th in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        print("  θ=%.2f lex %.4f | пул право тема %d/%d | пул не-право ∅ %d/%d" % (th, np.mean([top(p) == y and p[k] < th for p, y in L]),
              sum(top(p) in ys and p[k] < th for p, ys in W), len(W), sum(p[k] >= th for p in O), len(O)))
