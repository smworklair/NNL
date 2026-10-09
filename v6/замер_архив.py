# -*- coding: utf-8 -*-
"""v6, заявки на архиве: замер. Системы: В2б (база), Г (обе заявки с архивом), Г-п (только право.заявка3), Г-з (только здоровье.заявка4).
Наборы: общий тест 461, свежие 200 (calm_topic), свежие2 200 (архив, моя разметка), свежие3 200 (архив, разметка Muse Spark),
фразы Big Pickle 150. Пишет результаты/замер_архив.json. Запуск: python замер_архив.py"""
import collections
import json
import os
import sys

sys.dont_write_bytecode = True
V6 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V6)
from замер import NOT_KNOWN, jl, kernel, real_score  # noqa: E402

SYS = {"В2б": ["здоровье.заявка3", "здоровье.прил4", "право.заявка2", "право.знание2б"],
       "Г": ["здоровье.заявка4", "здоровье.прил4", "право.заявка3", "право.знание2б"],
       "Г-п": ["здоровье.заявка3", "здоровье.прил4", "право.заявка3", "право.знание2б"],
       "Г-з": ["здоровье.заявка4", "здоровье.прил4", "право.заявка2", "право.знание2б"]}
EXT = r"C:\ЯДРО-ОПЫТ\внешние"


def fresh3():
    texts = json.load(open(os.path.join(V6, "реальные", "архив", "свежие3_тексты.json"), encoding="utf-8"))
    out = []
    for r in jl(os.path.join(EXT, "разметка_свежие3.jsonl")):
        a = r["область"]
        areas = ["вне", "право", "здоровье"] if a == "спорно" else [a]
        out.append({"вопрос": texts[r["i"]]["текст"], "область": areas[0] if a != "спорно" else "спорно", "области": areas,
                    "ответы": r.get("ответы") or []})
    return out


def phrases(ask, rows):
    c = collections.Counter()
    for r in rows:
        a = ask(r["текст"])
        got = "вне" if a == NOT_KNOWN else a["область"]
        g = r["группа"]
        if g == "отрицание":
            g = "отрицание_своя_есть" if (r.get("своя_болезнь") or "").strip() else "отрицание_своей_нет"
        c[g, "n"] += 1
        c[g, got] += 1
    return {g: {k: c[g, k] for k in ("n", "здоровье", "право", "вне")} for g in sorted({k[0] for k in c})}


def main():
    bench = jl(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl")
    sets = {"свежие": jl(os.path.join(V6, "реальные", "разметка_свежие.jsonl")),
            "свежие2": jl(os.path.join(V6, "реальные", "архив", "разметка_свежие2.jsonl")),
            "свежие3": fresh3()}
    ph = jl(os.path.join(EXT, "фразы.jsonl"))
    out = {"системы": SYS}
    for s, names in SYS.items():
        k = kernel(names)
        ask = lambda t: k.ask(t)[0]
        res = {}
        c = collections.Counter()
        for r in bench:
            a = ask(r["вопрос"])
            c[r["область"], "n"] += 1
            c[r["область"], "ok"] += a != NOT_KNOWN and a["область"] == r["область"] and a["id"] == r["ответ"]
        res["общий_тест"] = {d: round(c[d, "ok"] / c[d, "n"], 4) for d in ("здоровье", "право")}
        for name, rows in sets.items():
            res[name] = real_score(ask, rows)
        res["фразы"] = phrases(ask, ph)
        out[s] = res
        print(s, json.dumps(res, ensure_ascii=False), flush=True)
    json.dump(out, open(os.path.join(V6, "результаты", "замер_архив.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
