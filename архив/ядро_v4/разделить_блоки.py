# -*- coding: utf-8 -*-
"""Шаг 2г: разделить блоки нового образца на «заявку» и «знание» БЕЗ переобучения (веса — те же массивы).
Плюс перештамп старых паспортов: отпечаток набора «общие» → отпечатки типов Запрос/Ответ (их схемы не менялись,
в набор добавлен только тип Направление). Запуск: python разделить_блоки.py"""
import json
import os
import shutil
import sys

V4 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V4)
sys.path.insert(0, os.path.join(V4, "архитектуры"))
from ядро.схема import Types, sha256_file  # noqa: E402
import общее as G  # noqa: E402

TY = Types(os.path.join(V4, "типы"))
FP = {t: TY.fingerprint(t) for t in ("общие:Запрос", "общие:Ответ", "общие:Направление")}


def restamp(folder):
    for d in sorted(os.listdir(folder)):
        p = os.path.join(folder, d, "паспорт.json")
        if not os.path.exists(p):
            continue
        ps = json.load(open(p, encoding="utf-8"))
        if "общие" in ps["типы"]:
            ps["перештамп"] = {"было": ps["типы"], "почему": "в набор «общие» добавлен тип Направление; схемы Запрос и Ответ не менялись"}
            ps["типы"] = {"общие:Запрос": FP["общие:Запрос"], "общие:Ответ": FP["общие:Ответ"]}
            json.dump(ps, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def split(src_root, dst_root):
    for area in ("здоровье", "право", "команды"):
        src = os.path.join(src_root, area)
        ps = json.load(open(os.path.join(src, "паспорт.json"), encoding="utf-8"))
        P = G.load_npz(os.path.join(src, "веса.npz"))
        classes = P.pop("классы")
        Z = {k[2:]: v for k, v in P.items() if k.startswith("Z_")}
        A = {k[2:]: v for k, v in P.items() if k.startswith("A_")}
        cfg = ps["настройки"]
        for name, arrays, arch, pin, pout, extra in (
                (area + ".заявка", Z, "заявка", {"тип": "общие:Запрос"}, {"тип": "общие:Направление", "условие": {"область": area}},
                 {"заявка": True, "роль": "знает, какие вопросы — области «%s» (ответов не знает)" % area}),
                (area, dict(A, классы=classes), "знание", {"тип": "общие:Направление", "условие": {"область": area}}, {"тип": "общие:Ответ"},
                 {"заявка": False, "роль": "знание области: " + ps["роль"], "ответы": ps["ответы"], "контроль": ps["контроль"]})):
            d = os.path.join(dst_root, name)
            os.makedirs(d, exist_ok=True)
            G.save_npz(os.path.join(d, "веса.npz"), arrays)
            n = int(sum(v.size for k, v in arrays.items() if k != "классы"))
            q = {"имя": name, "версия": 1, "область": area, "вход": pin, "выход": pout, "архитектура": arch,
                 "настройки": cfg, "веса": {"файл": "веса.npz", "sha256": sha256_file(os.path.join(d, "веса.npz")), "чисел": n},
                 "типы": {pin["тип"]: FP[pin["тип"]], pout["тип"]: FP[pout["тип"]]},
                 "обучение": dict(ps["обучение"], разделено_из=os.path.relpath(src, V4))}
            q.update(extra)
            if "контроль" in q:
                shutil.copy(os.path.join(src, "контроль.jsonl"), os.path.join(d, "контроль.jsonl"))
            json.dump(q, open(os.path.join(d, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("записан", d, "чисел", n)


if __name__ == "__main__":
    for f in ("блоки", "блоки_ф2", "блоки_ф2к"):
        restamp(os.path.join(V4, f))
    split(os.path.join(V4, "блоки_ф2к"), os.path.join(V4, "блоки_раздел"))
