# -*- coding: utf-8 -*-
"""Обучающий пул настоящих вопросов (Ответы Mail.ru, calm_topic, 1180 шт.), размеченный учителем (Claude): реальные/пул_метки.py.
Из пула выбрасываются почти-повторы любых проверочных вопросов (общий тест, зашумлённые, настоящие 154, отложенные 120,
свежие 200): сходство по кускам из 5 букв (Жаккар) ≥ 0,5. Возвращает строки для обучения по областям."""
import importlib.util
import json
import os
import re

V6 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL = os.path.join(V6, "реальные")
TESTS = [r"C:\ЯДРО-ОПЫТ\бенчмарки\bench\bench.jsonl", r"C:\Users\Admin\Documents\mailru_style\noisy_dev.jsonl",
         os.path.join(REAL, "разметка.jsonl"), os.path.join(REAL, "разметка_отложенные.jsonl"), os.path.join(REAL, "разметка_свежие.jsonl")]
NEAR = 0.5


def _grams(t):
    s = " ".join(re.findall(r"[а-яa-z0-9]+", t.lower().replace("ё", "е")))
    return {s[i:i + 5] for i in range(max(1, len(s) - 4))}


def _labels():
    spec = importlib.util.spec_from_file_location("пул_метки", os.path.join(REAL, "пул_метки.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_texts():
    out = []
    for p in TESTS:
        for l in open(p, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                out.append(r.get("вопрос") or r.get("text"))
    return out


def pool():
    """[{текст, право: [темы]|None, здоровье: [статьи]|None}] — без спорных и без почти-повторов проверочных вопросов.
    право/здоровье = None — вопрос не этой области; [] — этой области, без точного ответа."""
    texts = json.load(open(os.path.join(REAL, "пул_тексты.json"), encoding="utf-8"))
    M = _labels()
    tg = [_grams(t) for t in test_texts()]
    index = {}
    for j, g in enumerate(tg):
        for x in g:
            index.setdefault(x, []).append(j)
    rows, dropped = [], []
    for i, t in enumerate(texts):
        if i in M.SKIP:
            continue
        g = _grams(t)
        hits = {}
        for x in g:
            for j in index.get(x, ()):
                hits[j] = hits.get(j, 0) + 1
        near = max((c / len(g | tg[j]) for j, c in hits.items()), default=0.0)
        if near >= NEAR:
            dropped.append(i)
            continue
        rows.append({"i": i, "текст": t, "право": M.P.get(i), "здоровье": M.H.get(i)})
    return rows, dropped


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    rows, dropped = pool()
    texts = json.load(open(os.path.join(REAL, "пул_тексты.json"), encoding="utf-8"))
    print("в пуле", len(rows), "выброшено почти-повторов", len(dropped))
    for i in dropped:
        print("  ", i, texts[i][:120])
    print("право", sum(r["право"] is not None for r in rows), "здоровье", sum(r["здоровье"] is not None for r in rows),
          "вне", sum(r["право"] is None and r["здоровье"] is None for r in rows))
