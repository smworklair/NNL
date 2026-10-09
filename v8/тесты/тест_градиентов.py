# -*- coding: utf-8 -*-
"""Проверка ручных градиентов обучения конечными разностями (маленькая сеть из трёх блоков, float64)."""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
V8 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V8)
from обучение import сеть as С  # noqa: E402


def main():
    rng = np.random.RandomState(0)
    K = ["область:здоровье", "область:право", "глава:1", "акт:кас"]
    b1 = С.БлокУч("x", ["ответ:здоровье:1", "ответ:здоровье:2"], K[0:1] + K[2:3], ["область:право", "акт:кас"], корзины=50, размер=5, seed=1)
    b2 = С.БлокУч("y", ["ответ:право:a", "ответ:право:b", "ответ:право:c"], ["область:право", "акт:кас", "область:здоровье"],
                  ["область:здоровье", "глава:1"], корзины=40, размер=4, seed=2)
    b3 = С.БлокУч("z", ["ответ:право:q"], ["область:здоровье"], ["акт:кас", "глава:1"], корзины=30, размер=3, seed=3)
    for b in (b1, b2, b3):
        for k in b.P:
            b.P[k] = (rng.randn(*b.P[k].shape) * 0.5).astype(np.float64)
    rows = []
    for i in range(12):
        toks = ["с:t%d" % rng.randint(20) for _ in range(rng.randint(1, 6))]
        ans = [["ответ:здоровье:1"], ["ответ:право:b"], [], ["ответ:право:q", "ответ:право:a"]][i % 4]
        pon = {k: (None if rng.rand() < 0.2 else float(rng.rand() < 0.5)) for k in K}
        rows.append({"токены": toks, "ответы": ans, "понятия": pon})
    for смеш in ("среднее", "сумма"):
        сеть = С.Сеть([b1, b2, b3], проходов=2, смешивание=смеш, веса_смешивания={"y": 2.0})
        набор = С.Набор(rows, [b1, b2, b3], K)
        r = np.arange(len(rows))
        M = np.array([[1, 1, 1], [1, 0, 1], [0, 1, 1], [1, 1, 0]] * 3, np.float64)

        def f():
            l, a, _ = сеть.градиенты(набор, r, M, λ=0.7)
            return l + a
        _, _, G = сеть.градиенты(набор, r, M, λ=0.7)
        worst = 0.0
        for bi, b in enumerate(сеть.блоки):
            for k in ("A", "a", "U", "V", "b", "E"):
                P = b.P[k]
                if P.size == 0:
                    continue
                if k == "E":
                    uniq, gE = G[bi]["E"]
                    dense = np.zeros_like(P)
                    dense[uniq] = gE
                    g = dense
                else:
                    g = G[bi][k]
                for _ in range(6):
                    ix = tuple(rng.randint(s) for s in P.shape)
                    old = P[ix]
                    P[ix] = old + 1e-6
                    fp = f()
                    P[ix] = old - 1e-6
                    fm = f()
                    P[ix] = old
                    num = (fp - fm) / 2e-6
                    err = abs(num - g[ix]) / max(1e-6, abs(num) + abs(g[ix]))
                    worst = max(worst, err if abs(num) + abs(g[ix]) > 1e-7 else 0.0)
        print("смешивание %s: худшая относительная ошибка градиента %.2e" % (смеш, worst))
        assert worst < 1e-4, worst
    print("градиенты верны")


if __name__ == "__main__":
    main()
