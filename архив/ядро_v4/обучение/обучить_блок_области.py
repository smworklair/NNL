# -*- coding: utf-8 -*-
"""Обучение блока области нового образца — отдельно от всех других блоков (их веса и данные не читаются).
Сеть «ответ»: свои train-вопросы → свои классы. Сеть «заявка»: свои вопросы против стандартного фона.
Запуск: python обучение/обучить_блок_области.py --область здоровье|право|команды [--зерно 1] [--выход блоки/<область>]"""
import argparse
import datetime
import json
import os
import random
import sys

import numpy as np

V4 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V4)
sys.path.insert(0, os.path.join(V4, "архитектуры"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from ядро.схема import sha256_file  # noqa: E402
from обучение import данные  # noqa: E402
import общее as G  # noqa: E402
import текст as T  # noqa: E402

ROLE = {"здоровье": "статья Расписания болезней по фразе человека",
        "право": "правовая тема призыва по вопросу человека",
        "команды": "намерение голосовой команды (MASSIVE ru)"}
CFG = {"корзины_ответа": 1 << 16, "корзины_заявки": 1 << 14,
       "обучение_ответа": {"dim": 24, "lr": 0.005, "batch": 32, "epochs": 30, "patience": 4},
       "обучение_заявки": {"dim": 8, "lr": 0.005, "batch": 64, "epochs": 20, "patience": 3}}


def unthrottle():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class S(ctypes.Structure):
            _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
        k = ctypes.windll.kernel32
        hp = k.GetCurrentProcess()
        s = S(1, 1, 0)
        k.SetProcessInformation(hp, 4, ctypes.byref(s), ctypes.sizeof(s))
        k.SetPriorityClass(hp, 0x8000)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--область", required=True, choices=("здоровье", "право", "команды"))
    ap.add_argument("--зерно", type=int, default=1)
    ap.add_argument("--выход", default=None)
    ap.add_argument("--фон", type=int, default=1, help="версия стандарта фона: 1 или 2")
    ap.add_argument("--калибровка", type=float, default=0.0, help="доля своих dev-вопросов, которую блок готов отдать в «не знаю» (0 — без калибровки)")
    a = ap.parse_args()
    unthrottle()
    d = a.область
    out = a.выход or os.path.join(V4, "блоки", d)
    classes = данные.classes(d)
    ci = {c: i for i, c in enumerate(classes)}
    tr, dv = данные.domain_data(d, "train"), данные.domain_data(d, "dev")
    if a.фон == 2:   # фон v2 шире — заявке больше места
        CFG["корзины_заявки"], CFG["обучение_заявки"] = 1 << 15, dict(CFG["обучение_заявки"], dim=16)
    BA, BZ = CFG["корзины_ответа"], CFG["корзины_заявки"]

    # сеть «ответ»
    PA, logA = G.train_bag(BA, len(classes), [(T.features(t, BA), ci[y]) for t, y in tr],
                           [(T.features(t, BA), ci[y]) for t, y in dv], dict(CFG["обучение_ответа"], seed=a.зерно), log_prefix=d + "/ответ")
    # сеть «заявка»: 1 = моё, 0 = фон
    bg_tr, bg_dv = данные.background("train", a.фон), данные.background("dev", a.фон)
    ztr = [(T.features(t, BZ), 1) for t, _ in tr] + [(T.features(t, BZ), 0) for t in bg_tr]
    zdv = [(T.features(t, BZ), 1) for t, _ in dv] + [(T.features(t, BZ), 0) for t in bg_dv]
    cnt = np.bincount([y for _, y in ztr], minlength=2)
    cw = (len(ztr) / (2 * cnt)).tolist()
    PZ, logZ = G.train_bag(BZ, 2, ztr, zdv, dict(CFG["обучение_заявки"], seed=a.зерно), class_weight=cw, log_prefix=d + "/заявка")

    calib = {}
    if a.калибровка > 0:   # свой порог по своему dev: τ — квантиль заявок на своих dev-вопросах
        pz = np.array([float(G.forward(PZ, f)[1]) for f, _ in zdv if _ == 1])
        tau = float(min(0.99, max(0.01, np.quantile(pz, a.калибровка))))
        pb = np.array([float(G.forward(PZ, f)[1]) for f, y in zdv if y == 0])
        CFG["порог_калибровки"] = tau
        calib = {"доля_своих_dev_ниже": a.калибровка, "порог": round(tau, 6), "фон_dev_выше_порога": round(float((pb >= tau).mean()), 4)}
    arrays = {"A_" + k: v for k, v in PA.items()}
    arrays.update({"Z_" + k: v for k, v in PZ.items()})
    arrays["классы"] = np.array(classes)
    os.makedirs(out, exist_ok=True)
    wfile = os.path.join(out, "веса.npz")
    G.save_npz(wfile, arrays)
    # контрольный набор блока: 60 dev-вопросов, ожидание — ответ даёт этот блок (его область)
    rnd = random.Random(a.зерно)
    ctrl = rnd.sample(dv, min(60, len(dv)))
    with open(os.path.join(out, "контроль.jsonl"), "w", encoding="utf-8") as f:
        for t, _ in ctrl:
            f.write(json.dumps({"запрос": t, "ожидание": {"область": d}}, ensure_ascii=False) + "\n")
    n = int(sum(v.size for k, v in arrays.items() if k != "классы"))
    ps = {"имя": d, "версия": 1, "область": d, "роль": ROLE[d], "заявка": True,
          "вход": {"тип": "общие:Запрос"}, "выход": {"тип": "общие:Ответ"},
          "архитектура": "область", "настройки": CFG, "ответы": classes,
          "веса": {"файл": "веса.npz", "sha256": sha256_file(wfile), "чисел": n},
          "типы": {"общие": sha256_file(os.path.join(V4, "типы", "общие", "набор.json"))},
          "контроль": {"файл": "контроль.jsonl"},
          "обучение": {"скрипт": "обучение/обучить_блок_области.py", "зерно": a.зерно,
                       "когда": datetime.datetime.now().isoformat(timespec="seconds"),
                       "строк_ответа": len(tr), "dev_ответа": logA["лучший_dev"], "эпох_ответа": logA["эпох"],
                       "строк_заявки": len(ztr), "dev_заявки": logZ["лучший_dev"], "эпох_заявки": logZ["эпох"],
                       "калибровка": calib, "фон": a.фон, "фон_sha256": sha256_file(os.path.join(V4, "стандарт", "фон_train.jsonl" if a.фон == 1 else "фон%d_train.jsonl" % a.фон)),
                       "время_с": round(logA["время_с"] + logZ["время_с"], 1)}}
    with open(os.path.join(out, "паспорт.json"), "w", encoding="utf-8") as f:
        json.dump(ps, f, ensure_ascii=False, indent=1)
    print("записан", out, "чисел", n, "dev ответа", logA["лучший_dev"], "dev заявки", logZ["лучший_dev"])


if __name__ == "__main__":
    main()
