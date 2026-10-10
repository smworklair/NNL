# -*- coding: utf-8 -*-
"""Какие таблицы получаются «сложением оценок»?

Таблица T: строки 0..m-1, столбцы 0..n-1, в клетке номер ответа из 0..K-1.
Говорим, что T «получается сложением», если существуют числа A[y][r] и B[y][c] такие, что в каждой клетке (r, c)
ответ T[r][c] СТРОГО лучше всех остальных:  A[T][r] + B[T][c] > A[y][r] + B[y][c]  для всех y != T[r][c].

Проверка точная (дроби, без округлений): ищем «сертификат невозможности», то есть набор неравенств, которые в сумме дают
противоречие (теорема о переносе, Гордан). Нашли: таблица не получается. Не нашли: получается.

Запуск:  python таблицы.py            (счёт числа таблиц для небольших размеров)
         python таблицы.py латинские  (таблицы (r+c) mod n, n = 2..6)
         python таблицы.py латинские_все  (ВСЕ латинские квадраты порядков 3 и 4: 12 и 576 штук; около 3 минут)
         python таблицы.py нет2x2     (какие таблицы 2×2 при трёх ответах не получаются)
Только стандартная библиотека."""
import itertools
import sys
from fractions import Fraction


def матрица(T, m, n, K):
    пары = [(r, c, k) for r in range(m) for c in range(n) for k in range(K) if k != T[r][c]]
    M = [[Fraction(0)] * len(пары) for _ in range(K * (m + n))]
    for j, (r, c, k) in enumerate(пары):
        y = T[r][c]
        M[y * m + r][j] += 1
        M[k * m + r][j] -= 1
        M[K * m + y * n + c][j] += 1
        M[K * m + k * n + c][j] -= 1
    return пары, M


def сертификат(M):
    """Точный симплекс (правило Бланда): w >= 0, sum w = 1, M w = 0. Возвращает w или None."""
    m, N = len(M), len(M[0])
    A = [row[:] + [Fraction(0)] * (m + 1) for row in M] + [[Fraction(1)] * N + [Fraction(0)] * (m + 1)]
    b = [Fraction(0)] * m + [Fraction(1)]
    R = m + 1
    for i in range(R):
        A[i][N + i] = Fraction(1)
    базис = [N + i for i in range(R)]
    while True:
        цена = [Fraction(0)] * (N + R)
        for i in range(R):
            if базис[i] >= N:
                for j in range(N + R):
                    цена[j] -= A[i][j]
        for j in range(N, N + R):
            цена[j] += 1
        вход = next((j for j in range(N + R) if цена[j] < 0), None)
        if вход is None:
            break
        строка = min((b[i] / A[i][вход], базис[i], i) for i in range(R) if A[i][вход] > 0)[2]
        p = A[строка][вход]
        A[строка] = [x / p for x in A[строка]]
        b[строка] /= p
        for i in range(R):
            if i != строка and A[i][вход] != 0:
                f = A[i][вход]
                A[i] = [x - f * y for x, y in zip(A[i], A[строка])]
                b[i] -= f * b[строка]
        базис[строка] = вход
    if sum(b[i] for i in range(R) if базис[i] >= N) != 0:
        return None
    w = [Fraction(0)] * N
    for i in range(R):
        if базис[i] < N:
            w[базис[i]] = b[i]
    return w


def получается_сложением(T, m, n, K):
    if K == 1:
        return True
    пары, M = матрица(T, m, n, K)
    return сертификат(M) is None


def посчитать(m, n, K):
    всего = K ** (m * n)
    хорошо = 0
    for плоская in itertools.product(range(K), repeat=m * n):
        T = [плоская[r * n:(r + 1) * n] for r in range(m)]
        if получается_сложением(T, m, n, K):
            хорошо += 1
    return хорошо, всего


def латинские_квадраты(n):
    """Все латинские квадраты порядка n (перебор с возвратом)."""
    строки = []
    кв = [[None] * n for _ in range(n)]

    def ставим(поз):
        if поз == n * n:
            строки.append([r[:] for r in кв])
            return
        r, c = divmod(поз, n)
        for y in range(n):
            if y in кв[r][:c] or any(кв[i][c] == y for i in range(r)):
                continue
            кв[r][c] = y
            ставим(поз + 1)
            кв[r][c] = None
    ставим(0)
    return строки


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "латинские_все":
        for n in (3, 4):
            все = латинские_квадраты(n)
            хорошие = sum(1 for T in все if получается_сложением(T, n, n, n))
            print("порядок %d: латинских квадратов %d, получается сложением: %d" % (n, len(все), хорошие), flush=True)
    elif len(sys.argv) > 1 and sys.argv[1] == "нет2x2":
        for плоская in itertools.product(range(3), repeat=4):
            T = [плоская[0:2], плоская[2:4]]
            if not получается_сложением(T, 2, 2, 3):
                print("не получается:", T)
    elif len(sys.argv) > 1 and sys.argv[1].startswith("лат"):
        for n in range(2, 7):
            T = [[(r + c) % n for c in range(n)] for r in range(n)]
            print("(r + c) mod %d: %s" % (n, "получается" if получается_сложением(T, n, n, n) else "НЕ получается"))
    else:
        for (m, n, K) in ((2, 2, 2), (2, 3, 2), (3, 3, 2), (2, 2, 3), (2, 3, 3), (3, 3, 3)):
            х, в = посчитать(m, n, K)
            print("%d×%d, ответов %d: получается сложением %d из %d таблиц" % (m, n, K, х, в), flush=True)
