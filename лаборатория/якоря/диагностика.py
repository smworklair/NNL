# -*- coding: utf-8 -*-
"""Диагностика опыта «якоря» (после провала критериев; вердикт не меняет): исправен ли измерительный прибор.
Те же блоки, якоря (из якоря.json), данные. Классификатор — sklearn LogisticRegression (lbfgs, без перевеса классов).
Плюс «свои векторы» внутри блока без якорей — потолок того, что блок вообще различает."""
import json, os, sys
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import якоря as Y
import torch


class LR:
    """Логистическая регрессия (L-BFGS, L2), без перевеса классов — стандартный измерительный прибор."""
    def fit(self, X, y, l2=1e-2):
        X = torch.tensor(X, dtype=torch.float64); y = torch.tensor(y)
        self.W = torch.zeros(X.shape[1], 3, dtype=torch.float64, requires_grad=True)
        self.b = torch.zeros(3, dtype=torch.float64, requires_grad=True)
        opt = torch.optim.LBFGS([self.W, self.b], max_iter=500, line_search_fn="strong_wolfe")
        def closure():
            opt.zero_grad()
            loss = torch.nn.functional.cross_entropy(X @ self.W + self.b, y) + l2 * (self.W ** 2).sum()
            loss.backward(); return loss
        opt.step(closure)
        return self
    def score(self, X, y):
        with torch.no_grad():
            return float(((torch.tensor(X, dtype=torch.float64) @ self.W + self.b).argmax(1).numpy() == y).mean())


class StandardScaler:
    def fit(self, X):
        self.m, self.s = X.mean(0), X.std(0) + 1e-9; return self
    def transform(self, X):
        return (X - self.m) / self.s
tr, te = Y.labeled()
at = [x["текст"] for x in json.load(open(os.path.join(Y.OUT, "якоря.json"), encoding="utf-8"))]
ytr = np.array([Y.AREAS.index(y) for _, y in tr]); yte = np.array([Y.AREAS.index(y) for _, y in te])
perm = np.random.RandomState(7).permutation(len(at))
Xtr, Xte, Xp, Rtr, Rte = {}, {}, {}, {}, {}
for b in Y.BLOCKS:
    enc = Y.block_encoder(b); rel = Y.Relative(enc, at)
    Xtr[b], Xte[b], Xp[b] = rel([t for t, _ in tr]), rel([t for t, _ in te]), rel([t for t, _ in te], perm)
    Rtr[b], Rte[b] = enc([t for t, _ in tr]), enc([t for t, _ in te])
clf = lambda X, y: LR().fit(X, y)
print("доля самого частого класса %.3f" % (np.bincount(yte).max() / len(yte)))
print("\nсвои векторы блока (без якорей), учил и проверил на нём же:")
for b in Y.BLOCKS:
    s = StandardScaler().fit(Rtr[b]); m = clf(s.transform(Rtr[b]), ytr); print("  %-18s %.3f" % (b, m.score(s.transform(Rte[b]), yte)))
M = {A: clf(Xtr[A], ytr) for A in Y.BLOCKS}
print("\nякоря: строка — учил, столбец — проверил;  [в скобках — у проверяемого якоря перемешаны]")
print(" " * 20 + "".join("%-22s" % b for b in Y.BLOCKS))
for A in Y.BLOCKS:
    print("%-20s" % A + "".join("%-22s" % ("%.3f [%.3f]" % (M[A].score(Xte[B], yte), M[A].score(Xp[B], yte))) for B in Y.BLOCKS))
mf = clf(np.mean([Xtr[b] for b in Y.BLOCKS], 0), ytr)
print("\nсумма всех блоков %.3f" % mf.score(np.mean([Xte[b] for b in Y.BLOCKS], 0), yte))
for b in Y.BLOCKS:
    print("  без %-18s %.3f" % (b, mf.score(np.mean([Xte[x] for x in Y.BLOCKS if x != b], 0), yte)))
