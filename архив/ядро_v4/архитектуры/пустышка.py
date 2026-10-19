# -*- coding: utf-8 -*-
"""Блок-пустышка для тестов ядра (не модель). Вход: общие:Запрос. Выход: общие:Ответ.
Заявка: «жадный» — всегда 0.95; иначе 0.9, если в запросе есть слово из настроек, иначе 0.1.
Ответ: вид «выбор» — id = класс по длине запроса; вид «текст» — фиксированный текст из настроек.
Веса: массив w (его меняет дообучение) + список классов."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as G  # noqa: E402


def load(path, passport, types_dir):
    P = G.load_npz(path)
    classes = [str(c) for c in P.pop("классы")]
    return {"P": P, "classes": classes, "cfg": passport["настройки"], "area": passport["область"]}


def interface(obj):
    return {"классы": obj["classes"]}


def claim(obj, text):
    if obj["cfg"].get("жадный"):
        return 0.95
    return 0.9 if any(w in text for w in obj["cfg"]["слова"]) else 0.1


def run(obj, text):
    cfg = obj["cfg"]
    if cfg.get("режим") == "заявка":
        return {"область": obj["area"], "текст": text}
    if cfg.get("режим") == "знание":
        text = text["текст"]
    if cfg.get("вид") == "текст":
        return {"область": obj["area"], "вид": "текст", "текст": cfg["текст"], "p": 0.7}
    i = len(text) % len(obj["classes"])
    if cfg.get("ломает_тип"):
        return {"область": obj["area"], "вид": "выбор", "id": "чужой_id", "p": 0.5}
    return {"область": obj["area"], "вид": "выбор", "id": obj["classes"][i], "p": 0.8}


def params(obj):
    return dict(obj["P"])


def save(P, obj, path):
    G.save_npz(path, dict(P, классы=np.array(obj["classes"])))


def finetune(obj, data, settings):
    return {"w": obj["P"]["w"] + 1.0}, {"шагов": 1}
