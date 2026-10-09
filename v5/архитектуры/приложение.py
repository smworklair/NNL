# -*- coding: utf-8 -*-
"""Архитектура «приложение»: модель справочника призывника (TINY 1.6, вариант M+ambig) как блок-знание ядра.
Вход: общие:Направление[область=здоровье]. Выход: общие:Ответ (вид «выбор», id — номер статьи).

Что внутри (всё из файла весов блока):
  BM25 по словам и по кускам слов (индекс строится из текстов статей и обучающих фраз, лежащих в блоке),
  память фраз (ключи — эмбеддинги своей сети по словам и кускам слов), «крошка» — маленькая сеть,
  которая сводит три сигнала (word, char, netmem) в вероятности 88 статей + «ничего не подходит».
Код вычислений — модули проекта (train/*.py), только чтение; sha256 каждого файла записан в паспорте и сверяется
при загрузке: изменился код — блок не загрузится, ядро его не подключит."""
import hashlib
import json
import os
import sys

import numpy as np

sys.dont_write_bytecode = True            # ничего не писать в папку проекта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as G  # noqa: E402

PROJECT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"
TRAIN = os.path.join(PROJECT, "train")
CODE = ["lexical.py", "net.py", "crumb.py", "core_v2.py", "core_v3.py", "common.py"]


def code_hashes():
    return {f: hashlib.sha256(open(os.path.join(TRAIN, f), "rb").read()).hexdigest() for f in CODE}


def _modules():
    for p in (TRAIN, os.path.join(TRAIN, "teacher")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import torch  # noqa: F401
    import lexical
    import net as N
    import crumb as CR
    import core_v2
    import core_v3
    return lexical, N, CR, core_v2, core_v3


def _json(a):
    return json.loads(a.tobytes().decode("utf-8"))


def load(path, passport, types_dir):
    want = passport["настройки"]["код_sha256"]
    have = code_hashes()
    bad = [f for f in CODE if want.get(f) != have[f]]
    if bad:
        raise RuntimeError("код архитектуры в проекте изменился: %s" % bad)
    import torch
    lexical, N, CR, core_v2, core_v3 = _modules()
    P = G.load_npz(path)
    data, vocab = _json(P.pop("данные")), _json(P.pop("словарь"))
    v = N.Vocab.__new__(N.Vocab)
    v.w, v.c = vocab["w"], vocab["c"]
    m = N.BagNet(len(v.w), len(v.c), len(data["docs"]), dim=P["ew"].shape[1], hidden=0, drop=0.0)
    with torch.no_grad():
        m.ew.weight.copy_(torch.from_numpy(P["ew"]))
        m.ec.weight.copy_(torch.from_numpy(P["ec"]))
    m.eval()
    lex = lexical.Lexical(core_v2.expand(data["docs"], data["phrases"]))
    c = CR.Crumb.__new__(CR.Crumb)
    c.W1, c.b1, c.w2, c.b2 = P["crumb_W1"], P["crumb_b1"], P["crumb_w2"], float(P["crumb_b2"][0])
    mem_texts = [t for t, _ in data["mem"]]
    M = core_v3.keys(m, v, mem_texts)
    return {"P": P, "m": m, "v": v, "lex": lex, "c": c, "M": M, "ML": np.array([l for _, l in data["mem"]]),
            "tau": float(P["tau"][0]), "thr": float(P["thr"][0]), "sig": data["sig"], "cfg": passport["настройки"],
            "arts": [d["article_no"] for d in data["docs"]], "area": passport["область"],
            "mods": (core_v2, core_v3, CR)}


def interface(obj):
    return {"классы": obj["arts"]}


def probs(obj, texts):
    core_v2, core_v3, CR = obj["mods"]
    S = core_v2.signals(obj["lex"], [dict(text=t) for t in texts])
    S["netmem"] = core_v3.mem_scores(core_v3.keys(obj["m"], obj["v"], texts), obj["M"], obj["ML"], len(obj["arts"]), obj["tau"])
    return obj["c"].proba(CR.features({s: S[s] for s in obj["sig"]})[0])


def run(obj, value):
    p = probs(obj, [value["текст"]])[0]
    A = len(obj["arts"])
    pa = p[:A]
    order = np.argsort(-pa, kind="stable")[:5]
    cands = [[obj["arts"][i], float(pa[i])] for i in order]
    conf = cands[0][1]
    if obj["cfg"].get("ничего_как_отказ") and int(np.argmax(p)) == A:
        conf = 0.0      # приложение само решило «ничего не подходит» — передаём это ядру как нулевую уверенность
    return {"область": obj["area"], "вид": "выбор", "id": cands[0][0], "p": conf, "кандидаты": cands}


def decision(obj, text):
    """Решение самого приложения: 0 — назвать статью, 1 — уточнить, 2 — ничего не подходит (для сравнения, не для ядра)."""
    p = probs(obj, [text])[0]
    A = len(obj["arts"])
    top = int(np.argmax(p))
    return 2 if top == A else (0 if p[:A].max() >= obj["thr"] else 1)


def params(obj):
    return {k: obj["P"][k] for k in ("ew", "ec", "crumb_W1", "crumb_b1", "crumb_w2", "crumb_b2", "tau", "thr")}


def save(P, obj, path):
    raise NotImplementedError("блок приложения не дообучается через ядро (обучение — в проекте)")
