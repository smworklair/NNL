# -*- coding: utf-8 -*-
"""Оценка всех систем из ответы/*.jsonl на наборе замера. Пишет результаты/таблица.md и результаты/итог.json.

Срезы (по разметчику — потому что разметку делали ИИ, и флагман-разметчик может быть в выигрыше на своей разметке):
  свежие · Claude, свежие2 · Claude, свежие2 · Muse Spark, свежие2 · оба согласны, свежие3 · Muse Spark,
  всё · основная разметка (свежие и свежие2 — Claude, свежие3 — Muse Spark; как в замерах агентов).

Показатели (вопрос «спорно» — несколько допустимых областей — идёт только в «область верна»):
  область верна      — названная область среди допустимых («не знаю» NNL = «вне»);
  здоровье: статья   — вопросы здоровья с эталонными статьями: названа область «здоровье» и статья из эталона;
  право: тема        — то же для права;
  вне → вне          — вопрос не про призыв, система не взяла его (область «вне»);
  ответов            — сколько раз система назвала конкретную статью или тему;
  уверенных ошибок   — назвала статью или тему, а она неверна: не та статья или тема, не та область, или вопрос «вне»;
  отказ модели       — модель отказалась отвечать (у Anthropic — и ответ подстраховочной модели) — считается как «не знаю»;
  сбой               — технически нет ответа (не разобран JSON и т. п.) — вопрос исключается из счёта этой системы.
Системы с неполным покрытием (ручной замер) дополнительно сравниваются со всеми на своей выборке.
Запуск: python -I оценка.py"""
import glob
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from замер_общее import ОТВЕТЫ, ROOT, jl, набор  # noqa: E402

РЕЗ = os.path.join(ROOT, "результаты")


def срезы(rows):
    out = {}

    def add(name, items):
        out[name] = items

    for s, who in (("свежие", "Claude"), ("свежие2", "Claude"), ("свежие2", "Muse Spark"), ("свежие3", "Muse Spark")):
        add("%s · %s" % (s, who), [(r["ключ"], r["разметка"][who]) for r in rows if r["набор"] == s])
    agreed = []
    for r in rows:
        if r["набор"] != "свежие2":
            continue
        c, m = r["разметка"]["Claude"], r["разметка"]["Muse Spark"]
        if c["область"] == m["область"] and c["область"] != "спорно":
            both = sorted(set(c["ответы"]) & set(m["ответы"])) if c["ответы"] and m["ответы"] else []
            agreed.append((r["ключ"], {"область": c["область"], "области": [c["область"]], "ответы": both}))
    add("свежие2 · оба согласны", agreed)
    main_ = [(r["ключ"], r["разметка"]["Claude" if r["набор"] != "свежие3" else "Muse Spark"]) for r in rows]
    add("всё · основная разметка", main_)
    return out


def счёт(items, ans):
    c = dict.fromkeys(("вопросов", "область", "зд_n", "зд_ok", "пр_n", "пр_ok", "вне_n", "вне_ok", "ответов", "ошибок",
                       "отказ", "сбой"), 0)
    for key, g in items:
        a = ans.get(key)
        if a is None or a.get("сбой") == "нет ответа":
            c["сбой"] += a is not None
            continue
        c["вопросов"] += 1
        if a.get("сбой") == "отказ модели":
            c["отказ"] += 1
            area, idv = "вне", ""
        else:
            area, idv = a["область"], a.get("id") or ""
        c["область"] += area in g["области"]
        c["ответов"] += bool(idv)
        if g["область"] == "спорно":
            continue
        if g["область"] == "вне":
            c["вне_n"] += 1
            c["вне_ok"] += area == "вне"
            c["ошибок"] += bool(idv)
            continue
        if g["ответы"]:
            tag = "зд" if g["область"] == "здоровье" else "пр"
            good = area == g["область"] and idv in g["ответы"]
            c[tag + "_n"] += 1
            c[tag + "_ok"] += good
            c["ошибок"] += bool(idv) and not good
        else:
            c["ошибок"] += bool(idv) and area != g["область"]
    return c


def pct(a, b):
    return "%d/%d (%.0f%%)" % (a, b, 100.0 * a / b) if b else "—"


def строка(name, c):
    err = "%d (%.0f%% ответов)" % (c["ошибок"], 100.0 * c["ошибок"] / c["ответов"]) if c["ответов"] else str(c["ошибок"])
    return "| %s | %d | %s | %s | %s | %s | %d | %s | %d | %d |" % (
        name, c["вопросов"], pct(c["область"], c["вопросов"]), pct(c["зд_ok"], c["зд_n"]), pct(c["пр_ok"], c["пр_n"]),
        pct(c["вне_ok"], c["вне_n"]), c["ответов"], err, c["отказ"], c["сбой"])


ШАПКА = ["| система | вопросов | область верна | здоровье: статья | право: тема | вне → вне | ответов | уверенных ошибок | отказ модели | сбой |",
         "|---|---|---|---|---|---|---|---|---|---|"]


def main():
    rows = набор()
    systems = {}
    for path in sorted(glob.glob(os.path.join(ОТВЕТЫ, "*.jsonl"))):
        systems[os.path.basename(path)[:-6]] = {a["ключ"]: a for a in jl(path)}
    if not systems:
        sys.exit("нет ответов: запустите nnl.py, прогон.py или ручной.py")
    sl = срезы(rows)
    md, res = ["# Замер: NNL против флагманов", "",
               "Эталон — разметка ИИ (Claude, Muse Spark), не эксперта: это предварительный замер. Подробности — README.md.", ""], {}
    for name, items in sl.items():
        md += ["## %s (%d вопросов)" % (name, len(items)), ""] + ШАПКА
        res[name] = {}
        for s, ans in systems.items():
            c = счёт(items, ans)
            res[name][s] = c
            md.append(строка(s, c))
        md.append("")
    full = {s for s, ans in systems.items() if sum(1 for a in ans.values() if a.get("сбой") != "нет ответа") >= len(rows)}
    for s, ans in systems.items():
        if s in full:
            continue
        keys = {k for k, a in ans.items() if a.get("сбой") != "нет ответа"}
        if not keys:
            continue
        items = [(k, g) for k, g in sl["всё · основная разметка"] if k in keys]
        md += ["## Выборка системы %s (%d вопросов, основная разметка)" % (s, len(items)), ""] + ШАПКА
        res["выборка " + s] = {}
        for s2, ans2 in systems.items():
            c = счёт(items, ans2)
            res["выборка " + s][s2] = c
            md.append(строка(s2, c))
        md.append("")
    os.makedirs(РЕЗ, exist_ok=True)
    open(os.path.join(РЕЗ, "таблица.md"), "w", encoding="utf-8").write("\n".join(md))
    json.dump(res, open(os.path.join(РЕЗ, "итог.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    main()
