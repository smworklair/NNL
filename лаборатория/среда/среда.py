# -*- coding: utf-8 -*-
"""v9.1 среда (прозрачность): общее поле без знаний и без учёбы.
Форма зафиксирована: сведение (среднее писателей) + преломление (мягкое сжатие)
+ затвор (сверка записей с полем перед переписыванием). Своих обученных чисел нет."""
import numpy as np


def смешать(записи, Ki, K, присутствуют):
    """записи: {имя: вектор по своим понятиям} + пишет: {имя: [понятия]}.
    Возвращает поле m, присутствие pi, писателей {понятие: [имена]}."""
    nK = len(K)
    num = np.zeros(nK, np.float32)
    den = np.zeros(nK, np.float32)
    писатели = {}
    for имя, (c, пишет) in записи.items():
        if имя not in присутствуют:
            continue
        for j, k in enumerate(пишет):
            col = Ki[k]
            num[col] += c[j]
            den[col] += 1.0
            писатели.setdefault(k, []).append(имя)
    m = np.divide(num, den, out=np.zeros_like(num), where=den > 0)
    return m, (den > 0).astype(np.float32), писатели


def преломить(m, S=8.0, включить=True):
    """Преломление среды: пропускает, но преобразует. Фиксировано, не учится."""
    if not включить:
        return m
    return (S * np.tanh(m / S)).astype(np.float32)


def стробировать(mt, cols, tau):
    """Затвор отражений: запись сверяется с полем. tau=None — затвора нет."""
    if tau is None:
        return np.ones(len(cols), np.float32)
    return (1.0 / (1.0 + np.exp(-mt[cols] / tau))).astype(np.float32)
