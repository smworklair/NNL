# -*- coding: utf-8 -*-
"""v5, починка: Б0 (заявка v4), Б1 (заявка здоровья v2), Б2 (заявка v2 + спор заявок). Плюс А — приложение само.
Наборы: общий тест 461, зашумлённые 2051, настоящие 154 (видел до починки), отложенные 120 (не видел).
Пишет результаты/замер2.json. Запуск: python замер2.py"""
import collections
import json
import os
import sys

sys.dont_write_bytecode = True
V5 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V5)
from ядро import NOT_KNOWN, Kernel  # noqa: E402

B = os.path.join(V5, "блоки")
SYS = {"Б0": (["здоровье.заявка", "здоровье.прил", "право.заявка", "право"], False),
       "Б1": (["здоровье.заявка2", "здоровье.прил", "право.заявка", "право"], False),
       "Б2": (["здоровье.заявка2", "здоровье.прил", "право.заявка", "право"], True)}


def kernel(names, dispute):
    k = Kernel(os.path.join(V5, "типы"), os.path.join(V5, "архитектуры"), dispute=dispute)
    for n in names:
        ok, msg = k.attach(os.path.join(B, n))
        assert ok, (n, msg)
    return k


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def real_score(k, rows, A_run=None, A_dec=None):
    c = collections.Counter()
    for r in rows:
        if k is not None:
            a = k.ask(r["вопрос"])[0]
            got = "вне" if a == NOT_KNOWN else a["область"]
        c["n"] += 1
        c[r["область"], "n"] += 1
        if k is not None:
            c[r["область"], "обл"] += got == r["область"]
            if r["ответы"]:
                c[r["область"], "сотв"] += 1
                c[r["область"], "отв"] += got == r["область"] and a["id"] in r["ответы"]
        else:   # приложение само: только здоровье; «вне»/право — должно сказать «ничего» или хотя бы не называть статью
            if r["область"] == "здоровье" and r["ответы"]:
                c["здоровье", "сотв"] += 1
                c["здоровье", "отв"] += A_run(r["вопрос"])["id"] in r["ответы"]
            if r["область"] != "здоровье":
                d = A_dec(r["вопрос"])
                c["не_здоровье", "n"] += 1
                c["не_здоровье", "назвал"] += d == 0
                c["не_здоровье", "ничего"] += d == 2
    if k is None:
        return {"здоровье_верная_статья": "%d/%d" % (c["здоровье", "отв"], c["здоровье", "сотв"]),
                "не_здоровье_назвал_статью": "%d/%d" % (c["не_здоровье", "назвал"], c["не_здоровье", "n"]),
                "не_здоровье_ничего": "%d/%d" % (c["не_здоровье", "ничего"], c["не_здоровье", "n"])}
    out = {"область_угадана": round(sum(c[d, "обл"] for d in ("здоровье", "право", "вне")) / c["n"], 4)}
    for d in ("здоровье", "право", "вне"):
        out[d] = {"всего": c[d, "n"], "область_верна": c[d, "обл"]}
        if c[d, "сотв"]:
            out[d]["верный_ответ"] = "%d/%d" % (c[d, "отв"], c[d, "сотв"])
    return out


def main():
    bench = jl(r"C:\ЯДРО-ОПЫТ\бенчмарки\bench\bench.jsonl")
    noisy = jl(r"C:\Users\Admin\Documents\mailru_style\noisy_dev.jsonl")
    real = jl(os.path.join(V5, "реальные", "разметка.jsonl"))
    hold = jl(os.path.join(V5, "реальные", "разметка_отложенные.jsonl"))
    K = {s: kernel(n, d) for s, (n, d) in SYS.items()}
    app = next(k.blocks[n] for k in K.values() for n in k.blocks if n.startswith("здоровье.прил"))
    A_run = lambda t: app.arch.run(app.obj, {"область": "здоровье", "текст": t})
    A_dec = lambda t: app.arch.decision(app.obj, t)
    out = {"системы": {s: {"блоки": n, "спор": d} for s, (n, d) in SYS.items()}}
    res = {}
    for s, k in K.items():
        c = collections.Counter()
        for r in bench:
            a = k.ask(r["вопрос"])[0]
            c[r["область"], "n"] += 1
            c[r["область"], "ok"] += a != NOT_KNOWN and a["область"] == r["область"] and a["id"] == r["ответ"]
            c[r["область"], "нз"] += a == NOT_KNOWN
        res[s] = {d: {"доля": round(c[d, "ok"] / c[d, "n"], 4), "не_знаю": c[d, "нз"]} for d in ("здоровье", "право")}
    out["общий_тест"] = res
    print("ОБЩИЙ ТЕСТ:", res, flush=True)
    res = {}
    for s, k in K.items():
        c = collections.Counter()
        for r in noisy:
            a = k.ask(r["text"])[0]
            c[r["level"], "n"] += 1
            c[r["level"], "ok"] += a != NOT_KNOWN and a["область"] == "здоровье" and a["id"] == r["gold"]
        res[s] = {l: round(c[l, "ok"] / c[l, "n"], 4) for l in ("clean", "light", "medium", "heavy")}
    out["шум"] = res
    print("ШУМ:", res, flush=True)
    for name, rows in (("настоящие_154", real), ("отложенные_120", hold)):
        res = {s: real_score(k, rows) for s, k in K.items()}
        res["А"] = real_score(None, rows, A_run, A_dec)
        out[name] = res
        print(name.upper(), json.dumps(res, ensure_ascii=False), flush=True)
    json.dump(out, open(os.path.join(V5, "результаты", "замер2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
