# -*- coding: utf-8 -*-
"""Заявки права на dev (15 % пула + lex dev + фон dev): сколько своих выше 0,5 и сколько чужих. Проверочные наборы не читаются."""
import os, random, sys
sys.dont_write_bytecode = True
V6 = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, V6); sys.path.insert(0, os.path.join(V6, "архитектуры"))
sys.stdout.reconfigure(encoding="utf-8")
import json, numpy as np
from обучение import данные, реальные
import общее as G, текст as T, заявка as Z, знание as ZN
rows, _ = реальные.pool(); rnd = random.Random(1); rnd.shuffle(rows); cut = int(len(rows) * 0.15); p_dev = rows[:cut]
law = [r["текст"] for r in p_dev if r["право"] is not None]; oth = [r["текст"] for r in p_dev if r["право"] is None]
lex = [t for t, _ in данные.domain_data("право", "dev")]; bg = данные.background("dev", 2)
for name in sys.argv[1:]:
    ps = json.load(open(os.path.join(V6, "блоки", name, "паспорт.json"), encoding="utf-8"))
    obj = Z.load(os.path.join(V6, "блоки", name, "веса.npz"), ps, None)
    c = lambda ts, th=0.5: sum(Z.claim(obj, t) >= th for t in ts)
    for th in (0.5, 0.6, 0.7, 0.8):
        print(name, "θ=%.1f" % th, "lex %d/%d" % (c(lex, th), len(lex)), "пул право %d/%d" % (c(law, th), len(law)),
              "пул не-право %d/%d" % (c(oth, th), len(oth)), "фон %.4f" % (c(bg, th) / len(bg)))
P = G.load_npz(os.path.join(V6, "блоки", "право", "веса.npz")); cls = [str(x) for x in P.pop("классы")]
lt = [(r["текст"], r["право"]) for r in p_dev if r["право"]]
print("старое знание: пул тема %d/%d" % (sum(cls[int(np.argmax(G.forward(P, T.features(t, 1 << 16))))] in ys for t, ys in lt), len(lt)))
