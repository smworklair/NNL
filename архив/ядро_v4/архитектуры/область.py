# -*- coding: utf-8 -*-
"""Блок области нового образца (код без весов). Вход: общие:Запрос. Выход: общие:Ответ (вид «выбор»).
Две сети в одном файле весов:
  A_* — «ответ»: признаки текста → среднее векторов → линейный слой → классы области;
  Z_* — «заявка»: признаки текста → среднее векторов → «фон / моё»; claim() = вероятность «моё».
Блок самодостаточен: свой разбор текста (текст.py), ничего не берёт у других блоков."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as G  # noqa: E402
import текст as T  # noqa: E402


def load(path, passport, types_dir):
    P = G.load_npz(path)
    classes = [str(c) for c in P.pop("классы")]
    return {"A": {k[2:]: v for k, v in P.items() if k.startswith("A_")},
            "Z": {k[2:]: v for k, v in P.items() if k.startswith("Z_")},
            "classes": classes, "cfg": passport["настройки"], "area": passport["область"]}


def interface(obj):
    return {"классы": obj["classes"]}


def claim(obj, text):
    """Вероятность «моё». Если блок откалиброван на своём dev (порог_калибровки τ), шкала монотонно сдвигается так,
    что τ ↦ 0,5: тогда ядро с постоянным порогом 0,5 берёт ≈ 98 % своих вопросов блока."""
    p = float(G.forward(obj["Z"], T.features(text, obj["cfg"]["корзины_заявки"]))[1])
    tau = obj["cfg"].get("порог_калибровки")
    if not tau:
        return p
    return 0.5 + 0.5 * (p - tau) / (1.0 - tau) if p >= tau else 0.5 * p / tau


def run(obj, text):
    probs = G.forward(obj["A"], T.features(text, obj["cfg"]["корзины_ответа"]))
    cands = G.top(probs, obj["classes"])
    return {"область": obj["area"], "вид": "выбор", "id": cands[0][0], "p": cands[0][1], "кандидаты": cands}


def params(obj):
    P = {"A_" + k: v for k, v in obj["A"].items()}
    P.update({"Z_" + k: v for k, v in obj["Z"].items()})
    return P


def save(P, obj, path):
    G.save_npz(path, dict(P, классы=np.array(obj["classes"])))


def finetune(obj, data, settings):
    """data: [(Запрос, id)] — дообучается только сеть «ответ», заявка не меняется."""
    ci = {c: i for i, c in enumerate(obj["classes"])}
    B = obj["cfg"]["корзины_ответа"]
    rows = [(T.features(t, B), ci[y]) for t, y in data]
    cfg = dict(obj["cfg"]["обучение_ответа"])
    cfg.update(settings)
    PA, log = G.train_bag(B, len(ci), rows, [], cfg, init=obj["A"], log_prefix="дообучение")
    P = {"A_" + k: v for k, v in PA.items()}
    P.update({"Z_" + k: v for k, v in obj["Z"].items()})
    return P, log
