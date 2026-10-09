# -*- coding: utf-8 -*-
"""Обучение блока одной области — отдельно от блока разбора и от другой области (их веса не читаются).

Вход блока при обучении — ЭТАЛОННЫЙ разбор по правилу типа (типы/канон.py): основы вопроса, которые есть в словаре.
Блок разбора здесь не участвует: связь с ним — только через заранее заданный тип «Разбор».
Запуск: python обучение/обучить_область.py --область здоровье [--скрытый 0] [--dim 64] [--пары 1] [--зерно 1] [--выход ...]
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее_обучения as T  # noqa: E402
from общее_обучения import G, TYPES_DIR, V3  # noqa: E402

from обучение import данные  # noqa: E402
import мешок as A  # noqa: E402  (архитектуры/мешок.py)

ROLE = {"здоровье": "знает область «призыв по здоровью»: по основам вопроса называет статью Расписания болезней",
        "право": "знает область «право призыва»: по основам вопроса называет правовую тему"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--область", required=True, choices=данные.DOMAINS)
    ap.add_argument("--скрытый", type=int, default=0)
    ap.add_argument("--dim", type=int, default=64)
    ap.add_argument("--пары", type=int, default=1)
    ap.add_argument("--зерно", type=int, default=1)
    ap.add_argument("--имя", default=None)
    ap.add_argument("--выход", default=None)
    a = ap.parse_args()
    T.unthrottle()
    d = a.область
    name = a.имя or d
    out = a.выход or os.path.join(V3, "блоки", name)
    canon = G.load_canon(TYPES_DIR)
    vocab, vindex = G.load_vocab(TYPES_DIR)
    vset = set(vocab)
    import json
    with open(os.path.join(TYPES_DIR, "типы.json"), encoding="utf-8") as f:
        classes = json.load(f)["перечисления"]["Ответы"][d]
    ci = {c: i for i, c in enumerate(classes)}
    cfg = {"корзины_пар": 1 << 15, "пары": bool(a.пары),
           "обучение": {"dim": a.dim, "hidden": a.скрытый, "lr": 0.005, "batch": 32, "epochs": 30, "patience": 4, "seed": a.зерно}}

    def rows(split):
        return [(A.features(canon.reference_parse(t, vset), vindex, cfg), ci[y]) for t, y in данные.domain_data(d, split)]

    tr, dv = rows("train"), rows("dev")
    P, log = G.train_bag(A.n_features(vindex, cfg), len(classes), tr, dv, cfg["обучение"], log_prefix=name)
    arrays = dict(P)
    arrays["классы"] = np.array(classes)
    устройство = "линейная (мешок → вектор %d → классы)" % a.dim if not a.скрытый else \
        "со скрытым слоем (мешок → вектор %d → tanh %d → классы)" % (a.dim, a.скрытый)
    passport = {
        "имя": name, "версия": 1, "область": d, "роль": ROLE[d],
        "вход": {"тип": "Разбор", "условие": {"область": d}},
        "выход": {"тип": "Ответ", "условие": {"область": d}},
        "архитектура": "мешок", "устройство": устройство + (", пары основ" if a.пары else ", без пар основ"),
        "настройки": cfg,
        "зависит_от": ["типы/типы.json (словарь, Ответы.%s)" % d],
        "обучение": {"скрипт": "обучение/обучить_область.py", "зерно": a.зерно,
                     "данные": "train-части области «%s» (вопросы + официальные документы) → эталонный разбор типа" % d,
                     "строк": len(tr), "dev": log["лучший_dev"], "dev_строк": len(dv), "журнал": log},
    }
    T.write_block(out, passport, arrays)


if __name__ == "__main__":
    main()
