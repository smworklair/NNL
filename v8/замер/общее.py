# -*- coding: utf-8 -*-
"""Общее для замеров v8: системы (схема + блоки), наборы, подсчёт как в v6 и в замере флагманов."""
import collections
import importlib.util
import json
import os
import sys

sys.dont_write_bytecode = True
V8 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
БАЗА = os.path.dirname(V8)
sys.path.insert(0, V8)
from ядро import НЕ_ЗНАЮ, Схема, Ядро, Язык  # noqa: E402

ЯЗЫК_ПАПКА = os.path.join(V8, "язык")
ARCH = os.path.join(V8, "архитектуры")
БЛОКИ = os.path.join(V8, "блоки")


def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def система(вариант, зерно=1, язык=None, проверять_язык=True, схема=None):
    """Ядро с блоками варианта. Схема — схемы/<вариант>.json, если есть."""
    sp = схема or os.path.join(V8, "схемы", "%s.json" % вариант)
    k = Ядро(язык or Язык(ЯЗЫК_ПАПКА), ARCH, схема=sp if os.path.exists(sp) else None)
    папка = os.path.join(БЛОКИ, "%s.з%d" % (вариант, зерно))
    отчёты = {}
    for имя in sorted(os.listdir(папка)):
        p = os.path.join(папка, имя)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "паспорт.json")):
            ps = json.load(open(os.path.join(p, "паспорт.json"), encoding="utf-8"))
            if ps["обучение"].get("вариант") != вариант:      # блоки замены, дообучения и новые — не часть исходной системы
                continue
            ok, msg, отчёт = k.подключить(p, проверять_язык=проверять_язык)
            assert ok, (p, msg)
            отчёты[имя] = отчёт
    return k, отчёты


def наборы():
    v6 = os.path.join(БАЗА, "v6", "реальные")
    return {"общий_тест": jl(os.path.join(БАЗА, "bench", "bench.jsonl")),
            "настоящие_154": jl(os.path.join(v6, "разметка.jsonl")),
            "отложенные_120": jl(os.path.join(v6, "разметка_отложенные.jsonl")),
            "свежие_200": jl(os.path.join(v6, "разметка_свежие.jsonl")),
            "флагманский_600": jl(os.path.join(БАЗА, "флагманы", "набор", "набор.jsonl")),
            "отрицания_210": jl(os.path.join(v6, "отрицания.jsonl")),
            "фразы_150": jl(os.path.join(БАЗА, "внешние", "фразы.jsonl"))}


def область(a):
    return "вне" if a == НЕ_ЗНАЮ else a["область"]


def ид(a):
    return "" if a == НЕ_ЗНАЮ else (a.get("id") or "")


def общий_тест(k, rows):
    c = collections.Counter()
    for r in rows:
        a, rec = k.спросить(r["вопрос"])
        d = r["область"]
        top = rec["кандидаты"][0]["ответ"] if rec.get("кандидаты") else ""
        c[d, "n"] += 1
        c[d, "первый"] += top == "ответ:%s:%s" % (d, r["ответ"])
        c[d, "ответ_верен"] += a != НЕ_ЗНАЮ and a["вид"] == "ответ" and a["область"] == d and a["id"] == r["ответ"]
        c[d, "ответов"] += a != НЕ_ЗНАЮ and a["вид"] == "ответ"
        c[d, "уточнить"] += a != НЕ_ЗНАЮ and a["вид"] == "уточнить"
        c[d, "не_знаю"] += a == НЕ_ЗНАЮ
    return {d: {"вопросов": c[d, "n"], "первый_ответ_верен": round(c[d, "первый"] / c[d, "n"], 4),
                "ответ_верен": round(c[d, "ответ_верен"] / c[d, "n"], 4), "ответов": c[d, "ответов"],
                "уточнить": c[d, "уточнить"], "не_знаю": c[d, "не_знаю"]} for d in ("здоровье", "право")}


def живые(k, rows):
    """Как real_score в v6/замер.py: область угадана; по основной области — верный ответ."""
    c = collections.Counter()
    for r in rows:
        a, _ = k.спросить(r["вопрос"])
        got = область(a)
        ok_areas = r.get("области") or [r["область"]]
        grp = r["область"] if len(ok_areas) == 1 else "спорно"
        c["n"] += 1
        c["обл"] += got in ok_areas
        c[grp, "n"] += 1
        c[grp, "обл"] += got in ok_areas
        if r["ответы"] and grp != "спорно":
            c[grp, "сотв"] += 1
            c[grp, "отв"] += got == r["область"] and ид(a) in r["ответы"]
        if ид(a):
            c["ответов"] += 1
            wrong = grp == "вне" or (grp != "спорно" and not (got == r["область"] and (not r["ответы"] or ид(a) in r["ответы"])))
            c["ошибок"] += wrong
    out = {"область_угадана": "%d/%d" % (c["обл"], c["n"]), "ответов": c["ответов"], "уверенных_ошибок": c["ошибок"]}
    for g in ("здоровье", "право", "вне", "спорно"):
        if c[g, "n"]:
            out[g] = {"всего": c[g, "n"], "область_верна": c[g, "обл"]}
            if c[g, "сотв"]:
                out[g]["верный_ответ"] = "%d/%d" % (c[g, "отв"], c[g, "сотв"])
    return out


def отрицания(k, rows):
    c = collections.Counter()
    for r in rows:
        a, _ = k.спросить(r["текст"])
        v = r["вид"]
        c[v, "n"] += 1
        hid = None if a == НЕ_ЗНАЮ or a["область"] != "здоровье" or not ид(a) else ид(a)
        c[v, "верно"] += (hid in r["ответы"]) if r["ответы"] else (hid is None)
        c[v, "плохо"] += hid in r["плохо"]
        c[v, "не_знаю"] += a == НЕ_ЗНАЮ
    return {v: {"всего": c[v, "n"], "верно": c[v, "верно"], "назвал_отрицаемое": c[v, "плохо"], "не_знаю": c[v, "не_знаю"]}
            for v in ("есть", "нет", "смесь")}


def фразы(k, rows):
    c = collections.Counter()
    for r in rows:
        a, _ = k.спросить(r.get("текст", ""))
        g = r.get("группа", "?")
        c[g, "n"] += 1
        c[g, область(a)] += 1
        c[g, "с_ответом"] += bool(ид(a))
    return {g: {x: c[g, x] for x in ("n", "здоровье", "право", "вне", "с_ответом")} for g in sorted({k2[0] for k2 in c})}


def ответы_флагманского(k, rows):
    out = []
    for r in rows:
        a, rec = k.спросить(r["текст"])
        if a == НЕ_ЗНАЮ:
            out.append({"ключ": r["ключ"], "область": "вне", "id": "", "уверенность": None, "отказ": rec.get("причина")})
        else:
            out.append({"ключ": r["ключ"], "область": a["область"], "id": a.get("id") or "", "уверенность": a.get("p")})
    return out


def оценка_флагманов():
    """Функции срезов и счёта из флагманы/оценка.py (только чтение)."""
    fl = os.path.join(БАЗА, "флагманы")
    if fl not in sys.path:
        sys.path.insert(0, fl)
    spec = importlib.util.spec_from_file_location("оценка_флагманов", os.path.join(fl, "оценка.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
