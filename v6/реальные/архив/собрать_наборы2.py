# -*- coding: utf-8 -*-
"""Вторая выборка из архива Ответов Mail.ru (все 52 куска): пул3 — 3000 вопросов для разметки Claude Cowork (обучение),
свежие4 — 200 вопросов закрытого проверочного набора (разметка Muse Spark, флагманы). 65 % «Военная служба», 35 % армейские слова
в других разделах. Почти-повторы всех прежних наборов и друг друга выброшены. Зерно 9009."""
import glob, json, os, random, re, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from собрать_наборы import text, grams
SRC = r"C:\ЯДРО-ОПЫТ\данные\otvetmailru\куски"
OLD = []
for p in [r"C:\Users\Admin\Documents\mailru_style\calm_topic.jsonl", r"C:\Users\Admin\Documents\mailru_style\clean_seeds.jsonl",
          r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl", r"C:\Users\Admin\Documents\mailru_style\noisy_dev.jsonl",
          r"C:\ЯДРО-ОПЫТ\внешние\фразы.jsonl", r"C:\ЯДРО-ОПЫТ\флагманы\набор\набор.jsonl"]:
    if os.path.exists(p):
        OLD += [(lambda r: r.get("text") or r.get("вопрос") or r.get("текст"))(json.loads(l)) for l in open(p, encoding="utf-8") if l.strip()]
used = set()
for n in ("свежие2", "свежие3", "пул2"):
    for r in json.load(open(n + "_тексты.json", encoding="utf-8")):
        OLD.append(r["текст"]); used.add(r["qid"])
index, og = {}, []
for j, t in enumerate(OLD):
    g = grams(t or ""); og.append(g)
    for x in g: index.setdefault(x, set()).add(j)
A, K = [], []
for d in sorted(glob.glob(os.path.join(SRC, "*"))):
    A += [json.loads(l) for l in open(os.path.join(d, "армия.jsonl"), encoding="utf-8")]
    K += [json.loads(l) for l in open(os.path.join(d, "ключи.jsonl"), encoding="utf-8")]
rnd = random.Random(9009); rnd.shuffle(A); rnd.shuffle(K)
seen, it = [], {"армия": iter(A), "ключи": iter(K)}
def ok(r):
    if r["qid"] in used: return None
    t = text(r)
    if len(t) < 12: return None
    g = grams(t); c = {}
    for x in g:
        for j in index.get(x, ()): c[j] = c.get(j, 0) + 1
    if any(v / len(g | og[j]) >= 0.5 for j, v in c.items()): return None
    if any(len(g & h) / len(g | h) >= 0.5 for h in seen[-4000:]): return None
    seen.append(g); return t
out = {}
for name, (na, nk) in {"свежие4": (130, 70), "пул3": (1950, 1050)}.items():
    rows = []
    for kind, n in (("армия", na), ("ключи", nk)):
        got = 0
        while got < n:
            r = next(it[kind]); t = ok(r)
            if t: rows.append({"текст": t, "откуда": kind, "кат": r["кат"], "qid": r["qid"]}); got += 1
    rnd.shuffle(rows); out[name] = rows
    json.dump(rows, open(name + "_тексты.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump([{"i": i, "текст": r["текст"]} for i, r in enumerate(rows)],
              open(os.path.join(r"C:\ЯДРО-ОПЫТ\внешние", name + "_вопросы.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(name, len(rows))
