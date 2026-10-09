# -*- coding: utf-8 -*-
"""Шаг 1: блоки v3 БЕЗ переобучения на ядре v6. Веса копируются побайтно (sha сверяется), паспорта переписываются
в формат v4 (набор типов «военкомат_v3»). Успех — ответы на измерителе совпали с v3 461/461 (область, id, p).
Запуск: python шаг1_v3_на_ядре_v6.py"""
import json
import os
import shutil
import sys

V4 = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.join(os.path.dirname(V4), "v3")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V4)
from ядро import NOT_KNOWN, Kernel  # noqa: E402
from ядро.схема import sha256_file  # noqa: E402

OUT = os.path.join(V4, "блоки_v3")
TYPES = os.path.join(V4, "типы")
PORT = {"Текст": "военкомат_v3:Текст", "Разбор": "военкомат_v3:Разбор", "Ответ": "военкомат_v3:Ответ"}


def port(p):
    q = dict(p)
    q["тип"] = PORT[p["тип"]]
    return q


def main():
    tsha = sha256_file(os.path.join(TYPES, "военкомат_v3", "набор.json"))
    for name in ("разбор", "здоровье", "право"):
        src, dst = os.path.join(V3, "блоки", name), os.path.join(OUT, name)
        os.makedirs(dst, exist_ok=True)
        shutil.copy(os.path.join(src, "веса.npz"), os.path.join(dst, "веса.npz"))
        ps = json.load(open(os.path.join(src, "паспорт.json"), encoding="utf-8"))
        assert sha256_file(os.path.join(dst, "веса.npz")) == ps["веса"]["sha256"]
        ps["вход"], ps["выход"] = port(ps["вход"]), port(ps["выход"])
        ps["типы"] = {"военкомат_v3": tsha}
        ps["перенос"] = {"откуда": os.path.join(V3, "блоки", name), "типы_v3_sha256": ps.pop("типы_sha256"),
                         "что_изменено": "только паспорт (имена типов с набором, поле «типы»); веса побайтно те же"}
        json.dump(ps, open(os.path.join(dst, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    k = Kernel(TYPES, os.path.join(V4, "архитектуры"))
    for name in ("разбор", "здоровье", "право"):
        ok, msg = k.attach(os.path.join(OUT, name))
        print("подключён" if ok else "ОТКАЗ", name, "" if ok else msg)
        if not ok:
            sys.exit(1)
    print("план:", k.plan(), "чисел:", k.total_numbers())
    with open(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl", encoding="utf-8") as f:
        bench = [json.loads(l) for l in f if l.strip()]
    with open(os.path.join(V3, "результаты", "ответы_цепочка.jsonl"), encoding="utf-8") as f:
        v3ans = [json.loads(l) for l in f if l.strip()]
    same, ok_cnt = 0, {"здоровье": 0, "право": 0}
    for r, old in zip(bench, v3ans):
        a, rec = k.ask(r["вопрос"])
        same += json.dumps(rec["ответ"], ensure_ascii=False, sort_keys=True) == json.dumps(old["ответ"], ensure_ascii=False, sort_keys=True)
        ok_cnt[r["область"]] += a != NOT_KNOWN and a["область"] == r["область"] and a["id"] == r["ответ"]
    res = {"совпало_с_v3": "%d/%d" % (same, len(bench)), "верно": ok_cnt, "доля": round(sum(ok_cnt.values()) / len(bench), 4),
           "прошёл": same == len(bench)}
    os.makedirs(os.path.join(V4, "результаты"), exist_ok=True)
    json.dump(res, open(os.path.join(V4, "результаты", "шаг1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(res)


if __name__ == "__main__":
    main()
