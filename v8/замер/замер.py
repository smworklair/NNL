# -*- coding: utf-8 -*-
"""Замер качества систем v8 на проверочных наборах (ни один не использовался в обучении; почти-повторы выброшены из пулов).
Системы — варианты из обучение/обучить.py (зерно 1). Для сравнения — ответы систем v6 (В2б, Д) на флагманском наборе 600.
Пишет результаты/замер.з<зерно>.json и замер_флагманский.з<зерно>.md. Запуск: python замер/замер.py [варианты|все] [зерно]"""
import json
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as О  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ВАРИАНТЫ = ["основная", "один_проход", "без_выходных", "монолит"]


def main(варианты, зерно=1):
    t0 = time.time()
    Н = О.наборы()
    res = {"системы": {}, "наборы": {k: len(v) for k, v in Н.items()}}
    флаг = {}
    for v in варианты:
        k, отчёты = О.система(v, зерно)
        r = {"блоки": [b.кратко() for b in k.блоки.values()], "чисел": k.чисел_всего(), "проходов": k.схема.проходов,
             "проверка_языка": отчёты}
        r["общий_тест"] = О.общий_тест(k, Н["общий_тест"])
        for name in ("настоящие_154", "отложенные_120", "свежие_200"):
            r[name] = О.живые(k, Н[name])
        r["отрицания_210"] = О.отрицания(k, Н["отрицания_210"])
        r["фразы_150"] = О.фразы(k, Н["фразы_150"])
        отв = О.ответы_флагманского(k, Н["флагманский_600"])
        флаг["v8_" + v] = {a["ключ"]: a for a in отв}
        d = os.path.join(О.V8, "результаты", "ответы_600")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "v8_%s.з%d.jsonl" % (v, зерно)), "w", encoding="utf-8") as f:
            for a in отв:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        res["системы"][v] = r
        print(v, json.dumps(r["общий_тест"], ensure_ascii=False), "%.0f с" % (time.time() - t0), flush=True)
    # флагманский набор: срезы и счёт из флагманы/оценка.py; v6 — их готовые ответы
    M = О.оценка_флагманов()
    for name in ("nnl_В2б", "nnl_Д"):
        p = os.path.join(О.БАЗА, "флагманы", "ответы", name + ".jsonl")
        if os.path.exists(p):
            флаг["v6_" + name[4:]] = {a["ключ"]: a for a in О.jl(p)}
    sl = M.срезы(Н["флагманский_600"])
    res["флагманский_600"] = {s: {name: M.счёт(items, ans) for name, ans in флаг.items()} for s, items in sl.items()}
    os.makedirs(os.path.join(О.V8, "результаты"), exist_ok=True)
    out = os.path.join(О.V8, "результаты", "замер.з%d.json" % зерно)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # таблица флагманского набора в формате флагманы/оценка.py
    md = ["# Замер v8 на флагманском наборе 600 (разметка ИИ, как в флагманы/)", ""]
    for s, items in sl.items():
        md += ["## %s (%d вопросов)" % (s, len(items)), ""] + M.ШАПКА
        for name in флаг:
            md.append(M.строка(name, res["флагманский_600"][s][name]))
        md.append("")
    open(os.path.join(О.V8, "результаты", "замер_флагманский.з%d.md" % зерно), "w", encoding="utf-8").write("\n".join(md))
    print("\n".join(md[-12:]))
    print("записано", out, "%.0f с" % (time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1].split(",") if len(sys.argv) > 1 and sys.argv[1] != "все" else ВАРИАНТЫ, int(sys.argv[2]) if len(sys.argv) > 2 else 1)
