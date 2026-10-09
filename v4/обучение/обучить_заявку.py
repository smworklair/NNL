# -*- coding: utf-8 -*-
"""Обучение блока-заявки области «задачи» — отдельно от всех блоков. Сеть «моё / фон», калибровка на своём dev.
Свои: вопросы задачи/наборы/train.jsonl (генератор + GSM8K, ru+en). Чужие: стандарт фона v2 + английские фразы
Tatoeba (свои вопросы наполовину английские, а фон v2 русский — без них заявка брала бы любой английский текст;
это решение самого блока, другие блоки его не касается).
Запуск: python обучение/обучить_заявку.py [--зерно 1] [--выход блоки_задачи/задачи.заявка]"""
import argparse
import datetime
import json
import os
import sys

import numpy as np

V4 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V4)
sys.path.insert(0, os.path.join(V4, "архитектуры"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from ядро.схема import Types, sha256_file  # noqa: E402
from обучение import данные  # noqa: E402
import общее as G  # noqa: E402
import текст as T  # noqa: E402

CFG = {"корзины_заявки": 1 << 15, "обучение_заявки": {"dim": 16, "lr": 0.005, "batch": 64, "epochs": 20, "patience": 3}}


def rows(name):
    with open(os.path.join(V4, "задачи", "наборы", name + ".jsonl"), encoding="utf-8") as f:
        return [json.loads(l)["question"] for l in f if l.strip()]


def eng(split):
    with open(os.path.join(V4, "стандарт", "англ_фразы_%s.jsonl" % split), encoding="utf-8") as f:
        return [json.loads(l)["текст"] for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--зерно", type=int, default=1)
    ap.add_argument("--калибровка", type=float, default=0.02)
    ap.add_argument("--выход", default=os.path.join(V4, "блоки_задачи", "задачи.заявка"))
    a = ap.parse_args()
    B = CFG["корзины_заявки"]
    pos_tr, pos_dv = rows("train"), rows("dev")
    neg_tr = данные.background("train", 2) + eng("train")
    neg_dv = данные.background("dev", 2) + eng("dev")
    ztr = [(T.features(t, B), 1) for t in pos_tr] + [(T.features(t, B), 0) for t in neg_tr]
    zdv = [(T.features(t, B), 1) for t in pos_dv] + [(T.features(t, B), 0) for t in neg_dv]
    cnt = np.bincount([y for _, y in ztr], minlength=2)
    cw = (len(ztr) / (2 * cnt)).tolist()
    PZ, log = G.train_bag(B, 2, ztr, zdv, dict(CFG["обучение_заявки"], seed=a.зерно), class_weight=cw, log_prefix="задачи/заявка")
    pz = np.array([float(G.forward(PZ, f)[1]) for f, y in zdv if y == 1])
    pb = np.array([float(G.forward(PZ, f)[1]) for f, y in zdv if y == 0])
    tau = float(min(0.99, max(0.01, np.quantile(pz, a.калибровка))))
    cfg = dict(CFG, порог_калибровки=tau)
    os.makedirs(a.выход, exist_ok=True)
    w = os.path.join(a.выход, "веса.npz")
    G.save_npz(w, PZ)
    ty = Types(os.path.join(V4, "типы"))
    ps = {"имя": "задачи.заявка", "версия": 1, "область": "задачи", "заявка": True,
          "роль": "знает, какие вопросы — текстовые задачи (решать не умеет)",
          "вход": {"тип": "общие:Запрос"}, "выход": {"тип": "общие:Направление", "условие": {"область": "задачи"}},
          "архитектура": "заявка", "настройки": cfg,
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": int(sum(v.size for v in PZ.values()))},
          "типы": {"общие:Запрос": ty.fingerprint("общие:Запрос"), "общие:Направление": ty.fingerprint("общие:Направление")},
          "обучение": {"скрипт": "обучение/обучить_заявку.py", "зерно": a.зерно, "когда": datetime.datetime.now().isoformat(timespec="seconds"),
                       "свои": len(pos_tr), "чужие": len(neg_tr), "dev": log["лучший_dev"],
                       "калибровка": {"доля_своих_dev_ниже": a.калибровка, "порог": round(tau, 6), "фон_dev_выше_порога": round(float((pb >= tau).mean()), 4)}}}
    with open(os.path.join(a.выход, "паспорт.json"), "w", encoding="utf-8") as f:
        json.dump(ps, f, ensure_ascii=False, indent=1)
    print("записан", a.выход, "чисел", ps["веса"]["чисел"], "dev", log["лучший_dev"], "калибровка", ps["обучение"]["калибровка"])


if __name__ == "__main__":
    main()
