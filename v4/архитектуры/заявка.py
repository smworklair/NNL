# -*- coding: utf-8 -*-
"""Блок-заявка (код без весов): знает только, какие вопросы — его области. Ответов не знает.
Вход: общие:Запрос. Выход: общие:Направление {область, текст}. claim() — откалиброванная вероятность «моё»
(как в архитектуре «область»: сеть «моё/фон», сдвиг шкалы так, что свой порог τ ↦ 0,5)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as G  # noqa: E402
import текст as T  # noqa: E402


def load(path, passport, types_dir):
    return {"Z": G.load_npz(path), "cfg": passport["настройки"], "area": passport["область"]}


def interface(obj):
    return {}


def claim(obj, text):
    p = float(G.forward(obj["Z"], T.features(text, obj["cfg"]["корзины_заявки"]))[1])
    tau = obj["cfg"].get("порог_калибровки")
    if not tau:
        return p
    return 0.5 + 0.5 * (p - tau) / (1.0 - tau) if p >= tau else 0.5 * p / tau


def run(obj, text):
    return {"область": obj["area"], "текст": text}


def params(obj):
    return dict(obj["Z"])


def save(P, obj, path):
    G.save_npz(path, P)
