# -*- coding: utf-8 -*-
"""Быстрая проба маршрута без обучения: маркеры из заголовков -> точность выбора блока на бенче."""
import json, os, sys, collections
sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\v1\ядро")
from kernel import токены, стемы
ROOT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"

def load_jsonl(p):
    import json
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

docs = load_jsonl(os.path.join(ROOT, "train", "data", "docs_articles.jsonl"))
titles_h = {d["article_no"]: d.get("title","") for d in docs}
tops = json.load(open(os.path.join(ROOT, "rack", "data", "lex_topics.json"), encoding="utf-8"))
titles_l = {t["topic_id"]: t["title"] for t in tops}

def stems_of(t):
    return стемы(токены(t))

ch, cl, dh, dl = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
for t in titles_h.values():
    s = set(stems_of(t))
    for w in s: dh[w] += 1
for t in titles_l.values():
    s = set(stems_of(t))
    for w in s: dl[w] += 1
mh = set(w for w in dh if dl.get(w,0)==0 and len(w)>2)
ml = set(w for w in dl if dh.get(w,0)==0 and len(w)>2)
print("n_mark_h=%d n_mark_l=%d" % (len(mh), len(ml)))
bench = load_jsonl(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl")
ok = tot = 0
okh = toth = 0
okl = totl = 0
ref = 0
for r in bench:
    tot += 1
    s = set(stems_of(r["вопрос"]))
    sh, sl = len(s & mh), len(s & ml)
    pred = None
    if sh > sl and sh > 0: pred = "здоровье"
    elif sl > sh and sl > 0: pred = "право"
    else: ref += 1
    true = r["область"]
    if true == "здоровье": toth += 1
    else: totl += 1
    if pred == true:
        ok += 1
        if true == "здоровье": okh += 1
        else: okl += 1
    else:
        if true == "здоровье": pass
print("route_acc=%.3f health=%.3f(%d/%d) law=%.3f(%d/%d) refuse=%d/%d" % (
    ok/tot, okh/toth, okh, toth, okl/totl, okl, totl, ref, tot))
# примеры отказов и ошибок
shown = 0
for r in bench:
    s = set(stems_of(r["вопрос"]))
    sh, sl = len(s & mh), len(s & ml)
    pred = "здоровье" if (sh>sl and sh>0) else ("право" if (sl>sh and sl>0) else "не знаю")
    if pred != r["область"] and shown < 8:
        print("MISS true=%s pred=%s sh=%d sl=%d q=%s" % (r["область"], pred, sh, sl, r["вопрос"][:70]))
        shown += 1
