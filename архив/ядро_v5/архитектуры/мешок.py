# -*- coding: utf-8 -*-
"""Архитектура блока области «мешок» (код без весов).

Вход: значение типа Разбор (читает только поле «основы»). Выход: значение типа Ответ своей области.
Признаки: номер основы в словаре типа + (по настройке) пары соседних основ по хешу. Среднее векторов →
(скрытый слой tanh, если hidden > 0) → линейный слой → вероятности статей/тем.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as G  # noqa: E402


def features(stems, vindex, cfg):
    idx = [vindex[s] for s in stems]
    if cfg.get("пары", True):
        V, B = len(vindex), cfg["корзины_пар"]
        idx += [V + G.h("b:%s|%s" % (a, b), B) for a, b in zip(stems, stems[1:])]
    return idx


def n_features(vindex, cfg):
    return len(vindex) + (cfg["корзины_пар"] if cfg.get("пары", True) else 0)


def load(path, passport, types_dir):
    P = G.load_npz(path)
    classes = [str(c) for c in P.pop("классы")]
    _, vindex = G.load_vocab(types_dir)
    return {"P": P, "classes": classes, "vindex": vindex, "cfg": passport["настройки"],
            "domain": passport["выход"]["условие"]["область"]}


def interface(obj):
    return {"классы": obj["classes"]}


def run(obj, value):
    probs = G.forward(obj["P"], features(value["основы"], obj["vindex"], obj["cfg"]))
    cands = G.top(probs, obj["classes"])
    return {"область": obj["domain"], "id": cands[0][0], "p": cands[0][1], "кандидаты": cands}


def params(obj):
    return dict(obj["P"])


def save(P, obj, path):
    G.save_npz(path, dict(P, классы=np.array(obj["classes"])))


def finetune(obj, data, settings):
    """data: [(Разбор, id)]. Дообучение только этого блока, старт с его текущих весов."""
    cls = {c: i for i, c in enumerate(obj["classes"])}
    rows = [(features(x["основы"], obj["vindex"], obj["cfg"]), cls[y]) for x, y in data]
    cfg = dict(obj["cfg"]["обучение"])
    cfg.update(settings)
    P, log = G.train_bag(n_features(obj["vindex"], obj["cfg"]), len(cls), rows, [], cfg, init=obj["P"], log_prefix="дообучение")
    return P, log
