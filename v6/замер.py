# -*- coding: utf-8 -*-
"""v6: замер систем на всех наборах. Системы:
  Б4а — итог v5: заявка здоровья v3 + знание приложения со своим «ничего» + право v4 (заявка + знание);
  В1  — Б4а, но право v6 (заявка2 + знание2 со своим «∅»);
  В2  — В1 + знание здоровья просит ядро убирать отрицаемое (здоровье.прил4).
  А   — приложение само (только здоровье), для сравнения.
Наборы: общий тест 461, зашумлённые 2051, настоящие 154, отложенные 120, свежие 200 (главный, не виден до замера),
отрицания 210 (шаблоны), внешние (если есть файл C:\\ЯДРО-ОПЫТ\\внешние\\фразы.jsonl). Пишет результаты/замер.json."""
import collections
import json
import os
import sys

sys.dont_write_bytecode = True
V6 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V6)
from ядро import NOT_KNOWN, Kernel  # noqa: E402

B = os.path.join(V6, "блоки")
SYS = {"Б4а": ["здоровье.заявка3", "здоровье.прил3", "право.заявка", "право"],
       "В1": ["здоровье.заявка3", "здоровье.прил3", "право.заявка2", "право.знание2"],
       "В2": ["здоровье.заявка3", "здоровье.прил4", "право.заявка2", "право.знание2"],
       "В2б": ["здоровье.заявка3", "здоровье.прил4", "право.заявка2", "право.знание2б"]}   # не предсказывалась: «∅» права выключен
OUT = "замер.json"


def kernel(names):
    k = Kernel(os.path.join(V6, "типы"), os.path.join(V6, "архитектуры"))
    for n in names:
        ok, msg = k.attach(os.path.join(B, n))
        assert ok, (n, msg)
    return k


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def area_of(a):
    return "вне" if a == NOT_KNOWN else a["область"]


def real_score(ask, rows):
    """Настоящие фразы: область угадана (среди допустимых), по основной области — верный ответ."""
    c = collections.Counter()
    for r in rows:
        a = ask(r["вопрос"])
        got = area_of(a)
        ok_areas = r.get("области") or [r["область"]]
        grp = r["область"] if len(ok_areas) == 1 else "спорно"
        c["n"] += 1
        c["обл"] += got in ok_areas
        c[grp, "n"] += 1
        c[grp, "обл"] += got in ok_areas
        if r["ответы"] and grp != "спорно":
            c[grp, "сотв"] += 1
            c[grp, "отв"] += got == r["область"] and a["id"] in r["ответы"]
    out = {"область_угадана": "%d/%d" % (c["обл"], c["n"])}
    for g in ("здоровье", "право", "вне", "спорно"):
        if c[g, "n"]:
            out[g] = {"всего": c[g, "n"], "область_верна": c[g, "обл"]}
            if c[g, "сотв"]:
                out[g]["верный_ответ"] = "%d/%d" % (c[g, "отв"], c[g, "сотв"])
    return out


def app_real(A_run, A_dec, rows):
    """Приложение само: только здоровье; на не-здоровье хорошо — сказать «ничего»."""
    c = collections.Counter()
    for r in rows:
        if r["область"] == "здоровье" and r["ответы"]:
            c["сотв"] += 1
            c["отв"] += A_run(r["вопрос"])["id"] in r["ответы"]
        if "здоровье" not in (r.get("области") or [r["область"]]):
            d = A_dec(r["вопрос"])
            c["нз"] += 1
            c["ничего"] += d == 2
    return {"здоровье_верная_статья": "%d/%d" % (c["отв"], c["сотв"]), "не_здоровье_сказал_ничего": "%d/%d" % (c["ничего"], c["нз"])}


def neg_score(ask, rows):
    c = collections.Counter()
    for r in rows:
        a = ask(r["текст"])
        v = r["вид"]
        c[v, "n"] += 1
        hid = None if a == NOT_KNOWN or a["область"] != "здоровье" else a["id"]
        c[v, "верно"] += (hid in r["ответы"]) if r["ответы"] else (a == NOT_KNOWN)
        c[v, "плохо"] += hid in r["плохо"]
        c[v, "не_знаю"] += a == NOT_KNOWN
    return {v: {"всего": c[v, "n"], "верно": c[v, "верно"], "назвал_отрицаемое": c[v, "плохо"], "не_знаю": c[v, "не_знаю"]}
            for v in ("есть", "нет", "смесь")}


def main():
    bench = jl(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl")
    noisy = jl(r"C:\Users\Admin\Documents\mailru_style\noisy_dev.jsonl")
    sets = {"настоящие_154": jl(os.path.join(V6, "реальные", "разметка.jsonl")),
            "отложенные_120": jl(os.path.join(V6, "реальные", "разметка_отложенные.jsonl")),
            "свежие_200": jl(os.path.join(V6, "реальные", "разметка_свежие.jsonl"))}
    neg = jl(os.path.join(V6, "реальные", "отрицания.jsonl"))
    K = {s: kernel(n) for s, n in SYS.items()}
    app = K["Б4а"].blocks["здоровье.прил3"]
    A_run = lambda t: app.arch.run(app.obj, {"область": "здоровье", "текст": t})
    A_dec = lambda t: app.arch.decision(app.obj, t)
    out = {"системы": SYS, "чисел": {s: k.total_numbers() for s, k in K.items()}}

    res = {}
    for s, k in K.items():
        c = collections.Counter()
        for r in bench:
            a = k.ask(r["вопрос"])[0]
            c[r["область"], "n"] += 1
            c[r["область"], "ok"] += a != NOT_KNOWN and a["область"] == r["область"] and a["id"] == r["ответ"]
            c[r["область"], "нз"] += a == NOT_KNOWN
        res[s] = {d: {"доля": round(c[d, "ok"] / c[d, "n"], 4), "не_знаю": c[d, "нз"]} for d in ("здоровье", "право")}
    h = [r for r in bench if r["область"] == "здоровье"]
    res["А"] = {"здоровье": {"доля": round(sum(A_run(r["вопрос"])["id"] == r["ответ"] for r in h) / len(h), 4)}}
    out["общий_тест"] = res
    print("ОБЩИЙ ТЕСТ", json.dumps(res, ensure_ascii=False), flush=True)

    res = {}
    for s, k in K.items():
        c = collections.Counter()
        for r in noisy:
            a = k.ask(r["text"])[0]
            c[r["level"], "n"] += 1
            c[r["level"], "ok"] += a != NOT_KNOWN and a["область"] == "здоровье" and a["id"] == r["gold"]
        res[s] = {l: round(c[l, "ok"] / c[l, "n"], 4) for l in ("clean", "light", "medium", "heavy")}
    out["шум"] = res
    print("ШУМ", json.dumps(res, ensure_ascii=False), flush=True)

    for name, rows in sets.items():
        res = {s: real_score(lambda t, k=k: k.ask(t)[0], rows) for s, k in K.items()}
        res["А"] = app_real(A_run, A_dec, rows)
        out[name] = res
        print(name.upper(), json.dumps(res, ensure_ascii=False), flush=True)

    res = {s: neg_score(lambda t, k=k: k.ask(t)[0], neg) for s, k in K.items()}
    c = collections.Counter()
    for r in neg:
        hid = A_run(r["текст"])["id"]
        c[r["вид"], "n"] += 1
        c[r["вид"], "верно"] += hid in r["ответы"] if r["ответы"] else A_dec(r["текст"]) == 2
        c[r["вид"], "плохо"] += hid in r["плохо"] and A_dec(r["текст"]) != 2
    res["А"] = {v: {"всего": c[v, "n"], "верно": c[v, "верно"], "назвал_отрицаемое": c[v, "плохо"]} for v in ("есть", "нет", "смесь")}
    out["отрицания"] = res
    print("ОТРИЦАНИЯ", json.dumps(res, ensure_ascii=False), flush=True)

    ext = r"C:\ЯДРО-ОПЫТ\внешние\фразы.jsonl"
    if os.path.exists(ext):
        rows = jl(ext)
        res = {}
        for s, k in K.items():
            c = collections.Counter()
            for r in rows:
                a, rec = k.ask(r.get("текст", ""))
                g = r.get("группа", "?")
                c[g, "n"] += 1
                c[g, area_of(a)] += 1
            res[s] = {g: {x: c[g, x] for x in ("n", "здоровье", "право", "вне")} for g in sorted({k2[0] for k2 in c})}
        out["внешние"] = res
        print("ВНЕШНИЕ", json.dumps(res, ensure_ascii=False), flush=True)
    json.dump(out, open(os.path.join(V6, "результаты", OUT), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
