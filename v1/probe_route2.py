# -*- coding: utf-8 -*-
"""Проба 2: маркеры из полных текстов знаний (заголовки+критерии+пояснения vs темы+нормы)."""
import json, os, sys, collections
sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\v1\ядро")
from kernel import токены, стемы
ROOT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"

def load_jsonl(p):
    import json
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

docs = load_jsonl(os.path.join(ROOT, "train", "data", "docs_articles.jsonl"))
h_texts = []
for d in docs:
    h_texts.append(d.get("title","") + " " + " ".join(d.get("criteria") or []) + " " + " ".join(d.get("notes") or []))
tops = json.load(open(os.path.join(ROOT, "rack", "data", "lex_topics.json"), encoding="utf-8"))
prov = {p["id"]: p for p in load_jsonl(os.path.join(ROOT, "db", "provisions_v3.jsonl"))}
l_texts = []
for t in tops:
    s = t["title"]
    for pid in t.get("provision_ids", [])[:4]:
        p = prov.get(pid)
        if p and not p.get("repealed"):
            s += " " + (p.get("heading","") or "") + " " + (p.get("text_verbatim","") or "")[:400]
    l_texts.append(s)

def stems_of(t):
    return стемы(токены(t))

dh, dl = collections.Counter(), collections.Counter()
for t in h_texts:
    for w in set(stems_of(t)):
        dh[w] += 1
for t in l_texts:
    for w in set(stems_of(t)):
        dl[w] += 1
# маркеры: есть минимум в 2 документах своей области и ни разу в чужой
mh = set(w for w,c in dh.items() if c>=2 and dl.get(w,0)==0 and len(w)>3)
ml = set(w for w,c in dl.items() if c>=2 and dh.get(w,0)==0 and len(w)>3)
print("n_mark_h=%d n_mark_l=%d" % (len(mh), len(ml)))
bench = load_jsonl(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl")
ok=toth=totl=okh=okl=ref=0
tot=len(bench)
for r in bench:
    s=set(stems_of(r["вопрос"]))
    sh, sl = len(s&mh), len(s&ml)
    pred = "здоровье" if (sh>sl and sh>0) else ("право" if (sl>sh and sl>0) else "не знаю")
    if pred=="не знаю": ref+=1
    if r["область"]=="здоровье": toth+=1
    else: totl+=1
    if pred==r["область"]:
        ok+=1
        if r["область"]=="здоровье": okh+=1
        else: okl+=1
print("route_acc=%.3f health=%.3f(%d/%d) law=%.3f(%d/%d) refuse=%d/%d" % (ok/tot, okh/toth, okh, toth, okl/totl, okl, totl, ref, tot))
shown=0
for r in bench:
    s=set(stems_of(r["вопрос"]))
    sh, sl=len(s&mh), len(s&ml)
    pred="здоровье" if (sh>sl and sh>0) else ("право" if (sl>sh and sl>0) else "не знаю")
    if pred!=r["область"] and shown<10:
        print("MISS true=%s pred=%s sh=%d sl=%d q=%s" % (r["область"],pred,sh,sl,r["вопрос"][:70]))
        shown+=1
