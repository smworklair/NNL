# -*- coding: utf-8 -*-
"""Собирает набор для замера флагманов из уже размеченных наборов v6 (только чтение):

  свежие  — 200 вопросов calm_topic (Ответы Mail.ru), разметка Claude (учитель v6);
  свежие2 — 200 вопросов из архива Ответов Mail.ru, две разметки: Claude и Muse Spark (внешние/разметка_проверка.jsonl);
  свежие3 — 200 вопросов из архива, разметка Muse Spark.

Тексты — те же, что видят системы NNL в замерах агентов (байт в байт). Порядок подачи моделям перемешан (зерно 2026),
чтобы пачки не шли по наборам. Пишет набор/набор.jsonl и набор/набор.sha256.
Запуск: python -I собрать_набор.py"""
import collections
import json
import os
import random
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from замер_общее import НАБОР, V6, ВНЕШНИЕ, jl, sha256_file, write_jl  # noqa: E402

ЗЕРНО = 2026


def метка_claude(r):
    areas = r.get("области") or [r["область"]]
    return {"область": r["область"] if len(areas) == 1 else "спорно", "области": areas, "ответы": r["ответы"]}


def метка_muse(r):
    a = r["область"]
    return {"область": a, "области": ["вне", "право", "здоровье"] if a == "спорно" else [a], "ответы": r.get("ответы") or []}


def main():
    rows = []
    for r in jl(os.path.join(V6, "реальные", "разметка_свежие.jsonl")):
        rows.append({"ключ": "свежие:%d" % r["i"], "набор": "свежие", "i": r["i"], "текст": r["вопрос"],
                     "разметка": {"Claude": метка_claude(r)}})
    s2 = jl(os.path.join(V6, "реальные", "архив", "разметка_свежие2.jsonl"))
    m2 = jl(os.path.join(ВНЕШНИЕ, "разметка_проверка.jsonl"))
    q2 = json.load(open(os.path.join(ВНЕШНИЕ, "проверка_вопросы.json"), encoding="utf-8"))
    assert len(s2) == len(m2) == len(q2) == 200
    for r, m, q in zip(s2, m2, q2):
        assert r["i"] == m["i"] == q["i"] and r["вопрос"][:30].lower() == q["текст"][:30].lower(), r["i"]
        rows.append({"ключ": "свежие2:%d" % r["i"], "набор": "свежие2", "i": r["i"], "текст": r["вопрос"],
                     "разметка": {"Claude": метка_claude(r), "Muse Spark": метка_muse(m)}})
    t3 = json.load(open(os.path.join(V6, "реальные", "архив", "свежие3_тексты.json"), encoding="utf-8"))
    for m in jl(os.path.join(ВНЕШНИЕ, "разметка_свежие3.jsonl")):
        rows.append({"ключ": "свежие3:%d" % m["i"], "набор": "свежие3", "i": m["i"], "текст": t3[m["i"]]["текст"],
                     "разметка": {"Muse Spark": метка_muse(m)}})
    assert len({r["ключ"] for r in rows}) == len(rows) == 600
    random.Random(ЗЕРНО).shuffle(rows)
    for k, r in enumerate(rows):
        r["порядок"] = k
    write_jl(НАБОР, rows)
    sha = sha256_file(НАБОР)
    with open(os.path.join(os.path.dirname(НАБОР), "набор.sha256"), "w", encoding="utf-8") as f:
        f.write(sha + "  набор.jsonl\n")
    c = collections.Counter()
    for r in rows:
        for who, lab in r["разметка"].items():
            c[r["набор"], who, lab["область"]] += 1
    for k in sorted(c):
        print(*k, c[k])
    print("вопросов", len(rows), "sha256", sha)


if __name__ == "__main__":
    main()
