# -*- coding: utf-8 -*-
"""Блок-знание (код без весов): отвечает на вопросы своей области. Сам вопросы не выбирает — их направляет заявка.
Вход: общие:Направление[область=X]. Выход: общие:Ответ (вид «выбор»). Сеть — как «ответ» в архитектуре «область»."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as G  # noqa: E402
import текст as T  # noqa: E402


def load(path, passport, types_dir):
    P = G.load_npz(path)
    classes = [str(c) for c in P.pop("классы")]
    return {"A": P, "classes": classes, "cfg": passport["настройки"], "area": passport["область"]}


def interface(obj):
    return {"классы": obj["classes"]}


NOTHING = "∅"     # класс «ничего не подходит», если блок обучен с ним (v6); у старых блоков его нет — поведение прежнее


def run(obj, value):
    probs = G.forward(obj["A"], T.features(value["текст"], obj["cfg"]["корзины_ответа"]))
    if NOTHING not in obj["classes"]:
        cands = G.top(probs, obj["classes"])
        return {"область": obj["area"], "вид": "выбор", "id": cands[0][0], "p": cands[0][1], "кандидаты": cands}
    k = obj["classes"].index(NOTHING)
    cands = [c for c in G.top(probs, obj["classes"], k=6) if c[0] != NOTHING][:5]
    th = obj["cfg"].get("порог_ничего")          # «∅» при p(∅) ≥ порога; без порога — когда «∅» самый вероятный
    nothing = probs[k] >= th if th is not None else int(probs.argmax()) == k
    conf = 0.0 if nothing else cands[0][1]        # блок сам решил «ничего не подходит» — нулевая уверенность
    return {"область": obj["area"], "вид": "выбор", "id": cands[0][0], "p": conf, "кандидаты": cands}


def params(obj):
    return dict(obj["A"])


def save(P, obj, path):
    G.save_npz(path, dict(P, классы=np.array(obj["classes"])))


def finetune(obj, data, settings):
    """data: [(Направление, id)] — дообучение только этого знания."""
    ci = {c: i for i, c in enumerate(obj["classes"])}
    B = obj["cfg"]["корзины_ответа"]
    rows = [(T.features(v["текст"], B), ci[y]) for v, y in data]
    cfg = dict(obj["cfg"]["обучение_ответа"])
    cfg.update(settings)
    return G.train_bag(B, len(ci), rows, [], cfg, init=obj["A"], log_prefix="дообучение")
