# -*- coding: utf-8 -*-
"""Выбор знания права и порога «∅» по ОДНОМУ счёту на dev: заявка2 (порог 0,5) → знание.
Верно: правовой вопрос (lex dev, пул dev с темой) — заявка взяла и тема верна; не-право (пул dev) — «не знаю». Проверочные наборы не читаются."""
import os, random, sys, json
sys.dont_write_bytecode = True
V6 = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, V6); sys.path.insert(0, os.path.join(V6, "архитектуры"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from обучение import данные, реальные
import общее as G, текст as T, заявка as Z, знание as ZN
rows, _ = реальные.pool(); rnd = random.Random(1); rnd.shuffle(rows); cut = int(len(rows) * 0.15); p_dev = rows[:cut]
L = [(t, [y]) for t, y in данные.domain_data("право", "dev")] + [(r["текст"], r["право"]) for r in p_dev if r["право"]]
O = [r["текст"] for r in p_dev if r["право"] is None]
ps = json.load(open(os.path.join(V6, "блоки", "право.заявка2", "паспорт.json"), encoding="utf-8"))
zo = Z.load(os.path.join(V6, "блоки", "право.заявка2", "веса.npz"), ps, None)
cl = {t: Z.claim(zo, t) >= 0.5 for t in [t for t, _ in L] + O}
best = []
for name in ("право.знание2", "право.знание2_ф0к2", "право.знание2_ф1000к2", "право.знание2_ф0к1"):
    P = G.load_npz(os.path.join(V6, "блоки", name, "веса.npz")); cls = [str(c) for c in P.pop("классы")]; k = cls.index(ZN.NOTHING)
    pr = {t: G.forward(P, T.features(t, 1 << 16)) for t in cl}
    def top(p):
        q = p.copy(); q[k] = -1; return cls[int(np.argmax(q))]
    for th in (None, 0.5, 0.7, 0.9, 0.95, 0.98):
        ab = lambda p: th is not None and p[k] >= th
        ok_l = sum(cl[t] and not ab(pr[t]) and top(pr[t]) in ys for t, ys in L)
        ok_o = sum((not cl[t]) or ab(pr[t]) for t in O)
        best.append((ok_l + ok_o, name, th, ok_l, ok_o))
        print("%-24s θ=%-5s право %d/%d не-право %d/%d всего %d/%d" % (name, th, ok_l, len(L), ok_o, len(O), ok_l + ok_o, len(L) + len(O)))
print("ЛУЧШИЙ", sorted(best, key=lambda x: -x[0])[0])
