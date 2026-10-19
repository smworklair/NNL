# -*- coding: utf-8 -*-
"""v9.1 загрузка воткнутых блоков: готовые веса v8, НЕ переучивать.
Блок здесь — коннектор: пишет в поле и читает поле. Сам по себе не отвечает."""
import json
import os
import sys

import numpy as np

V8 = r"C:\ЯДРО-ОПЫТ\система"
sys.path.insert(0, os.path.join(V8, "архитектуры"))
import мешок_шина as МШ  # noqa: E402
sys.path.insert(0, V8)
from ядро import Язык  # noqa: E402

ЯЗЫК = Язык(os.path.join(V8, "язык"))
ПАПКА = os.path.join(V8, "блоки", "основная_внешние.з1")


def загрузить(имя):
    p = os.path.join(ПАПКА, имя)
    ps = json.load(open(os.path.join(p, "паспорт.json"), encoding="utf-8"))
    z = np.load(os.path.join(p, "веса.npz"), allow_pickle=False)
    cfg = ps["настройки"]
    return {"имя": имя, "ответы": [str(x) for x in z["ответы"].tolist()],
            "пишет": [str(x) for x in z["пишет"].tolist()], "читает": [str(x) for x in z["читает"].tolist()],
            "P": {k: np.array(z[k], dtype=np.float32) for k in ("E", "A", "a", "U", "V", "b")},
            "B": int(cfg["корзины"]), "d": int(cfg["размер"]), "L": float(cfg["граница"]),
            "соль": str(cfg["соль"]), "свёртка": str(cfg.get("свёртка", "корень")),
            "масштаб": float(cfg.get("масштаб_чтения", 1.0))}


def токены(текст):
    return ЯЗЫК.перевести(текст)["токены"]


def кодировать(б, ток):
    idx = МШ.индексы(б["соль"], ток, б["B"]).astype(np.int64)
    h = б["P"]["E"][idx].sum(axis=0) / np.float32(np.sqrt(len(ток)))
    return idx, h.astype(np.float32)
