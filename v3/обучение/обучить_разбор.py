# -*- coding: utf-8 -*-
"""Обучение блока «разбор» — отдельно от блоков областей (их нет и они не читаются).

Сеть «область»: тексты обучающих частей обеих областей, метка = область (веса классов уравнены).
Сеть «нормализатор»: формы слов из тех же текстов + искусственные опечатки → основа словаря типа (без меток областей).
Запуск: python обучение/обучить_разбор.py [--выход блоки/разбор] [--зерно 1]
"""
import argparse
import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее_обучения as T  # noqa: E402
from общее_обучения import G, TYPES_DIR, V3  # noqa: E402

from обучение import данные  # noqa: E402
import разбор as A  # noqa: E402  (архитектуры/разбор.py)

ALPHA = "абвгдежзийклмнопрстуфхцчшщъыьэюя"

CFG = {"корзины_области": 1 << 16, "корзины_нормализатора": 1 << 16, "порог_p": 0.5, "порог_сходства": 0.8,
       "обучение_области": {"dim": 16, "lr": 0.005, "batch": 32, "epochs": 30, "patience": 4},
       "обучение_нормализатора": {"dim": 48, "lr": 0.005, "batch": 256, "epochs": 15, "patience": 3}}


def corrupt(w, rnd):
    w = list(w)
    for _ in range(1 if len(w) < 8 else rnd.choice((1, 2))):
        op, i = rnd.randrange(4), rnd.randrange(1, len(w))
        if op == 0 and len(w) > 4:
            del w[i]
        elif op == 1:
            w.insert(i, rnd.choice(ALPHA))
        elif op == 2:
            w[i] = rnd.choice(ALPHA)
        elif i < len(w) - 1:
            w[i], w[i + 1] = w[i + 1], w[i]
    return "".join(w)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--выход", default=os.path.join(V3, "блоки", "разбор"))
    ap.add_argument("--зерно", type=int, default=1)
    a = ap.parse_args()
    T.unthrottle()
    canon = G.load_canon(TYPES_DIR)
    vocab, vindex = G.load_vocab(TYPES_DIR)
    domains = list(данные.DOMAINS)
    cfg = dict(CFG)

    # --- сеть «область» ---
    tr, dv = [], []
    for i, d in enumerate(domains):
        tr += [(A.dom_features(canon.content_words(t), cfg), i) for t, _ in данные.domain_data(d, "train")]
        dv += [(A.dom_features(canon.content_words(t), cfg), i) for t, _ in данные.domain_data(d, "dev")]
    cnt = np.bincount([y for _, y in tr], minlength=len(domains))
    cw = (len(tr) / (len(domains) * cnt)).tolist()
    dcfg = dict(cfg["обучение_области"], seed=a.зерно)
    Pd, logd = G.train_bag(cfg["корзины_области"], len(domains), tr, dv, dcfg, class_weight=cw, log_prefix="область")

    # --- сеть «нормализатор» ---
    forms = set()
    for d in domains:
        for t, _ in данные.domain_data(d, "train"):
            forms.update(w for w in canon.content_words(t) if A.normalizable(w))
    forms = sorted(forms)
    rnd = random.Random(a.зерно)
    rnd.shuffle(forms)
    n_dev = len(forms) // 20
    def rows(ws, k):
        out = []
        for w in ws:
            y = vindex[canon.stem(w)]
            out.append((A.norm_features(w, cfg), y))
            out += [(A.norm_features(corrupt(w, rnd), cfg), y) for _ in range(k)]
        return out
    ntr, ndv = rows(forms[n_dev:], 6), rows(forms[:n_dev], 2)
    ncfg = dict(cfg["обучение_нормализатора"], seed=a.зерно)
    Pn, logn = G.train_bag(cfg["корзины_нормализатора"], len(vocab), ntr, ndv, ncfg, log_prefix="нормализатор")

    arrays = {"dom_" + k: v for k, v in Pd.items()}
    arrays.update({"norm_" + k: v for k, v in Pn.items()})
    arrays["области"] = np.array(domains)
    with open(os.path.join(TYPES_DIR, "типы.json"), encoding="utf-8") as f:
        arrays["словарь_sha256"] = np.array(json.load(f)["словарь"]["sha256"])
    passport = {
        "имя": "разбор", "версия": 1, "область": "общий (все области)",
        "роль": "разбирает вопрос: определяет область и сводит слова к основам словаря типа (исправляет опечатки и формы)",
        "вход": {"тип": "Текст"}, "выход": {"тип": "Разбор"},
        "архитектура": "разбор", "настройки": cfg,
        "зависит_от": ["типы/типы.json (Область, словарь)", "типы/канон.py"],
        "обучение": {"скрипт": "обучение/обучить_разбор.py", "зерно": a.зерно,
                     "данные_области": "train-части обеих областей (вопросы + документы), метка = область; dev — dev-части",
                     "строк_области": len(tr), "dev_области": logd["лучший_dev"], "журнал_области": logd,
                     "данные_нормализатора": "формы слов из тех же текстов + 6 искусственных опечаток на форму, без меток",
                     "форм_слов": len(forms), "строк_нормализатора": len(ntr), "dev_нормализатора": logn["лучший_dev"],
                     "журнал_нормализатора": {k: v for k, v in logn.items() if k != "ход"}},
    }
    T.write_block(a.выход, passport, arrays)


if __name__ == "__main__":
    main()
