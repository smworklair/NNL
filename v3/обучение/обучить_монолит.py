# -*- coding: utf-8 -*-
"""Монолит для сравнения: ОДНА модель той же семьи, обученная целиком на тех же данных (объединение данных всех блоков).
Не блок: в ядро не подключается.

  --вход текст  : сырой текст → основы, пары основ, куски слов 3–5 букв (всё по хешу) → 132 класса   [главное сравнение]
  --вход основы : эталонный разбор типа (ровно то, что проходит через «Разбор») → 132 класса           [разбор причин]
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее_обучения as T  # noqa: E402
from общее_обучения import G, TYPES_DIR, V3  # noqa: E402

from обучение import данные  # noqa: E402
import мешок  # noqa: E402

BUCKETS = 1 << 17


def text_features(text, canon):
    st = canon.stems(text)
    idx = [G.h("u:" + s, BUCKETS) for s in st]
    idx += [G.h("b:%s|%s" % (x, y), BUCKETS) for x, y in zip(st, st[1:])]
    for w in canon.content_words(text):
        idx += [G.h("c:" + g, BUCKETS) for g in G.char_ngrams(w, 3, 5)]
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--вход", choices=("текст", "основы"), default="текст")
    ap.add_argument("--зерно", type=int, default=1)
    ap.add_argument("--выход", default=None)
    a = ap.parse_args()
    T.unthrottle()
    canon = G.load_canon(TYPES_DIR)
    vocab, vindex = G.load_vocab(TYPES_DIR)
    vset = set(vocab)
    with open(os.path.join(TYPES_DIR, "типы.json"), encoding="utf-8") as f:
        answers = json.load(f)["перечисления"]["Ответы"]
    classes = ["%s:%s" % (d, i) for d in данные.DOMAINS for i in answers[d]]
    ci = {c: i for i, c in enumerate(classes)}
    bag_cfg = {"корзины_пар": 1 << 15, "пары": True}
    if a.вход == "текст":
        feat, n_feat = (lambda t: text_features(t, canon)), BUCKETS
    else:
        feat, n_feat = (lambda t: мешок.features(canon.reference_parse(t, vset), vindex, bag_cfg)), мешок.n_features(vindex, bag_cfg)
    tr, dv = [], []
    for d in данные.DOMAINS:
        tr += [(feat(t), ci["%s:%s" % (d, y)]) for t, y in данные.domain_data(d, "train")]
        dv += [(feat(t), ci["%s:%s" % (d, y)]) for t, y in данные.domain_data(d, "dev")]
    cfg = {"dim": 64, "hidden": 0, "lr": 0.005, "batch": 32, "epochs": 30, "patience": 4, "seed": a.зерно}
    P, log = G.train_bag(n_feat, len(classes), tr, dv, cfg, log_prefix="монолит-" + a.вход)
    out = a.выход or os.path.join(V3, "сравнение", "монолит" if a.вход == "текст" else "монолит_основы")
    os.makedirs(out, exist_ok=True)
    G.save_npz(os.path.join(out, "веса.npz"), dict(P, классы=np.array(classes)))
    desc = {"что": "монолит для сравнения (не блок)", "вход": a.вход, "классов": len(classes),
            "чисел": int(sum(v.size for v in P.values())), "настройки": cfg, "корзины": n_feat,
            "данные": "объединение train-частей обеих областей (те же, что у блоков); dev — объединение dev",
            "строк": len(tr), "dev": log["лучший_dev"], "журнал": log}
    with open(os.path.join(out, "описание.json"), "w", encoding="utf-8") as f:
        json.dump(desc, f, ensure_ascii=False, indent=1)
    print("записан", out, "чисел:", desc["чисел"])


if __name__ == "__main__":
    main()
