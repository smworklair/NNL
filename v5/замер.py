# -*- coding: utf-8 -*-
"""v5: модель приложения внутри ядра. Системы: А — приложение само по себе; Б — ядро + знание здоровья из приложения;
В — ядро + знание здоровья v4. Наборы: общий тест (461), зашумлённые фразы здоровья (2051), настоящие фразы (154).
Плюс контроль: вынуть знание здоровья. Пишет результаты/замер.json. Запуск: python замер.py"""
import collections
import json
import os
import sys

sys.dont_write_bytecode = True
V5 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V5)
sys.path.insert(0, os.path.join(V5, "архитектуры"))
from ядро import NOT_KNOWN, Kernel  # noqa: E402

B = os.path.join(V5, "блоки")
SYS = {"Б": ["здоровье.заявка", "здоровье.прил", "право.заявка", "право"], "В": ["здоровье.заявка", "здоровье", "право.заявка", "право"]}


def kernel(names):
    k = Kernel(os.path.join(V5, "типы"), os.path.join(V5, "архитектуры"))
    for n in names:
        ok, msg = k.attach(os.path.join(B, n))
        assert ok, (n, msg)
    return k


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main():
    out = {}
    bench = jl(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl")
    noisy = jl(r"C:\Users\Admin\Documents\mailru_style\noisy_dev.jsonl")
    real = jl(os.path.join(V5, "реальные", "разметка.jsonl"))
    K = {s: kernel(n) for s, n in SYS.items()}
    app = K["Б"].blocks["здоровье.прил"]          # тот же объект — для системы А (без ядра)
    A_run = lambda t: app.arch.run(app.obj, {"область": "здоровье", "текст": t})
    A_dec = lambda t: app.arch.decision(app.obj, t)

    # 1. общий тест
    res = {}
    for s in ("Б", "В"):
        c = collections.Counter()
        for r in bench:
            a = K[s].ask(r["вопрос"])[0]
            c[r["область"], "n"] += 1
            if a == NOT_KNOWN:
                c[r["область"], "не_знаю"] += 1
            elif a["область"] == r["область"] and a["id"] == r["ответ"]:
                c[r["область"], "верно"] += 1
        res[s] = {d: {"доля": round(c[d, "верно"] / c[d, "n"], 4), "не_знаю": c[d, "не_знаю"]} for d in ("здоровье", "право")}
    h = [r for r in bench if r["область"] == "здоровье"]
    res["А"] = {"здоровье": {"доля": round(sum(A_run(r["вопрос"])["id"] == r["ответ"] for r in h) / len(h), 4)}}
    out["общий_тест"] = res
    print("ОБЩИЙ ТЕСТ:", res, flush=True)

    # 2. зашумлённые фразы здоровья
    lv = sorted({r["level"] for r in noisy}, key=["clean", "light", "medium", "heavy"].index if all(
        x in ["clean", "light", "medium", "heavy"] for x in {r["level"] for r in noisy}) else None)
    res = {}
    for s in ("А", "Б", "В"):
        c = collections.Counter()
        for r in noisy:
            if s == "А":
                ok = A_run(r["text"])["id"] == r["gold"]
            else:
                a = K[s].ask(r["text"])[0]
                ok = a != NOT_KNOWN and a["область"] == "здоровье" and a["id"] == r["gold"]
            c[r["level"], "n"] += 1
            c[r["level"], "ok"] += ok
        res[s] = {l: round(c[l, "ok"] / c[l, "n"], 4) for l in lv}
    out["шум"] = {"уровни": {l: sum(1 for r in noisy if r["level"] == l) for l in lv}, "доли": res}
    print("ЗАШУМЛЁННЫЕ:", out["шум"], flush=True)

    # 3. настоящие фразы
    res, rows = {}, []
    for s in ("Б", "В"):
        c = collections.Counter()
        for r in real:
            a, rec = K[s].ask(r["вопрос"])
            got = "вне" if a == NOT_KNOWN else a["область"]
            c["n"] += 1
            c[r["область"], "n"] += 1
            c[r["область"], "область_верно"] += (got == r["область"])
            if r["ответы"]:
                c[r["область"], "с_ответом"] += 1
                c[r["область"], "ответ_верно"] += (got == r["область"] and a["id"] in r["ответы"])
            if s == "Б":
                rows.append({"i": r["i"], "вопрос": r["вопрос"], "метка": r["область"], "ответы": r["ответы"],
                             "Б": None if a == NOT_KNOWN else [a["область"], a["id"], round(a["p"], 3)], "заявки": rec.get("заявки")})
        res[s] = {"область_угадана": round(sum(c[d, "область_верно"] for d in ("здоровье", "право", "вне")) / c["n"], 4)}
        for d in ("здоровье", "право", "вне"):
            res[s][d] = {"всего": c[d, "n"], "область_верно": c[d, "область_верно"]}
            if c[d, "с_ответом"]:
                res[s][d]["ответ_верно"] = "%d/%d" % (c[d, "ответ_верно"], c[d, "с_ответом"])
    hh = [r for r in real if r["область"] == "здоровье" and r["ответы"]]
    na = [r for r in real if r["область"] != "здоровье"]
    res["А"] = {"здоровье_ответ_верно": "%d/%d" % (sum(A_run(r["вопрос"])["id"] in r["ответы"] for r in hh), len(hh)),
                "не_здоровье_назвал_статью": "%d/%d" % (sum(A_dec(r["вопрос"]) == 0 for r in na), len(na)),
                "не_здоровье_уточнил": "%d/%d" % (sum(A_dec(r["вопрос"]) == 1 for r in na), len(na)),
                "не_здоровье_ничего": "%d/%d" % (sum(A_dec(r["вопрос"]) == 2 for r in na), len(na))}
    out["настоящие"] = res
    json.dump(rows, open(os.path.join(V5, "результаты", "настоящие_ответы_Б.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("НАСТОЯЩИЕ:", json.dumps(res, ensure_ascii=False), flush=True)

    # 4. контроль: вынуть знание здоровья в системе Б
    k = K["Б"]
    before = [k.ask(r["вопрос"])[1]["ответ"] for r in bench]
    k.detach("здоровье.прил")
    mid = [k.ask(r["вопрос"])[1] for r in bench]
    ok, msg = k.attach(os.path.join(B, "здоровье.прил"))
    after = [k.ask(r["вопрос"])[1]["ответ"] for r in bench]
    hi = [i for i, r in enumerate(bench) if r["область"] == "здоровье"]
    li = [i for i, r in enumerate(bench) if r["область"] == "право"]
    out["контроль"] = {
        "вынуто_здоровье_вопросы_здоровья_не_знаю": "%d/%d" % (sum(mid[i]["ответ"] == NOT_KNOWN for i in hi), len(hi)),
        "вынуто_здоровье_право_не_изменилось": "%d/%d" % (sum(json.dumps(mid[i]["ответ"], sort_keys=True) == json.dumps(before[i], sort_keys=True) for i in li), len(li)),
        "вернули_совпало": "%d/%d" % (sum(json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True) for a, b in zip(before, after)), len(bench)),
        "причина_отказа": next((m.get("отказ") for m in mid if m["ответ"] == NOT_KNOWN), None)}
    print("КОНТРОЛЬ:", out["контроль"], flush=True)
    out["чисел"] = {s: K[s].total_numbers() for s in K}
    json.dump(out, open(os.path.join(V5, "результаты", "замер.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("чисел:", out["чисел"])


if __name__ == "__main__":
    main()
