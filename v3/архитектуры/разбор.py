# -*- coding: utf-8 -*-
"""Архитектура блока «разбор» (код без весов). Вход: Текст. Выход: Разбор.

Что делает:
  1) слова и основы — по эталонному правилу типа (типы/канон.py);
  2) основа есть в словаре типа — берётся как есть;
     основы нет (опечатка, другая форма слова) — сеть-нормализатор по кускам букв предлагает основу словаря;
     замена принимается, только если p ≥ порог_p и основы похожи по буквам (≥ порог_сходства), иначе слово выбрасывается;
     слова с цифрами и короче 4 букв не нормализуются;
  3) область — сеть «область» по словам и кускам слов 3–5 букв.
Обе сети лежат в одном файле весов (параметры dom_* и norm_*).
"""
import difflib
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as G  # noqa: E402


def dom_features(words, cfg):
    B = cfg["корзины_области"]
    idx = [G.h("w:" + w, B) for w in words]
    for w in words:
        idx += [G.h("c:" + g, B) for g in G.char_ngrams(w, 3, 5)]
    return idx


def norm_features(word, cfg):
    B = cfg["корзины_нормализатора"]
    return [G.h("w:" + word, B)] + [G.h("c:" + g, B) for g in G.char_ngrams(word, 2, 4)]


def normalizable(word):
    return len(word) >= 4 and not any(ch.isdigit() for ch in word)


def load(path, passport, types_dir):
    P = G.load_npz(path)
    domains = [str(x) for x in P.pop("области")]
    vsha = str(P.pop("словарь_sha256"))
    vocab, vindex = G.load_vocab(types_dir)
    return {"dom": {k[4:]: v for k, v in P.items() if k.startswith("dom_")},
            "norm": {k[5:]: v for k, v in P.items() if k.startswith("norm_")},
            "domains": domains, "vsha": vsha, "vocab": vocab, "vindex": vindex,
            "canon": G.load_canon(types_dir), "cfg": passport["настройки"]}


def interface(obj):
    return {"области": obj["domains"], "словарь_sha256": obj["vsha"]}


def run(obj, text):
    canon, cfg, vindex = obj["canon"], obj["cfg"], obj["vindex"]
    words = canon.content_words(text)
    stems, repl = [], []
    for w in words:
        s = canon.stem(w)
        if s in vindex:
            stems.append(s)
        elif normalizable(w):
            probs = G.forward(obj["norm"], norm_features(w, cfg))
            j = int(np.argmax(probs))
            cand, p = obj["vocab"][j], float(probs[j])
            if p >= cfg["порог_p"] and difflib.SequenceMatcher(None, s, cand).ratio() >= cfg["порог_сходства"]:
                stems.append(cand)
                repl.append([w, cand, p])
    pd = G.forward(obj["dom"], dom_features(words, cfg))
    d = obj["domains"][int(np.argmax(pd))]
    return {"область": d, "p_область": {obj["domains"][i]: float(pd[i]) for i in range(len(pd))},
            "основы": stems, "замены": repl}


def params(obj):
    P = {"dom_" + k: v for k, v in obj["dom"].items()}
    P.update({"norm_" + k: v for k, v in obj["norm"].items()})
    return P


def save(P, obj, path):
    G.save_npz(path, dict(P, области=np.array(obj["domains"]), словарь_sha256=np.array(obj["vsha"])))


def finetune(obj, data, settings):
    """data: [(Текст, область)] — дообучается только сеть «область»; нормализатор не меняется."""
    di = {d: i for i, d in enumerate(obj["domains"])}
    words = obj["canon"].content_words
    rows = [(dom_features(words(t), obj["cfg"]), di[y]) for t, y in data]
    cfg = dict(obj["cfg"]["обучение_области"])
    cfg.update(settings)
    P, log = G.train_bag(obj["cfg"]["корзины_области"], len(di), rows, [], cfg, init=obj["dom"], log_prefix="дообучение")
    out = {"dom_" + k: v for k, v in P.items()}
    out.update({"norm_" + k: v for k, v in obj["norm"].items()})
    return out, log
