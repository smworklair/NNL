# -*- coding: utf-8 -*-
"""Совпадают ли ошибки разных систем на общем тесте. Только чтение."""
import collections
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
S = sys.argv[1]
bench = [json.loads(l) for l in open(r"C:\ЯДРО-ОПЫТ\бенчмарки\bench\bench.jsonl", encoding="utf-8") if l.strip()]
pred = {}
for f in ("v4.json", "v6.json"):
    pred.update(json.load(open(S + "/" + f, encoding="utf-8")))
sp = json.load(open(r"C:\ЯДРО-ОПЫТ\внешние\справочник.json", encoding="utf-8"))
name = {x["id"]: x["название"] for x in sp["статьи_болезней"] + sp["правовые_темы"]}

TRIO = {"здоровье": ["TINY_1.6", "v4_знание", "v3_цепочка"], "право": ["v4_знание", "v3_цепочка", "NNL_Д"]}
out = {}
for dom, systems in TRIO.items():
    idx = [i for i, r in enumerate(bench) if r["область"] == dom]
    n = len(idx)
    acc = {s: sum(pred[s][i] == bench[i]["ответ"] for i in idx) / n for s in systems}
    exp_all_wrong = 1.0
    for s in systems:
        exp_all_wrong *= 1 - acc[s]
    hist = collections.Counter(sum(pred[s][i] == bench[i]["ответ"] for s in systems) for i in idx)
    all_wrong = [i for i in idx if all(pred[s][i] != bench[i]["ответ"] for s in systems)]
    agree = []
    for i in all_wrong:
        c = collections.Counter(pred[s][i] for s in systems if pred[s][i] is not None)
        top, cnt = c.most_common(1)[0] if c else (None, 0)
        if cnt >= 2:
            agree.append((i, top, cnt))
    print("=" * 100)
    print("%s: %d вопросов; точность: %s" % (dom, n, ", ".join("%s %.3f" % (s, a) for s, a in acc.items())))
    print("сколько систем из 3 ответили верно:", dict(sorted(hist.items())))
    print("ошиблись все три: %d (%.1f%%); если бы ошибки были независимы, ожидалось бы %.1f%%" % (
        len(all_wrong), 100 * len(all_wrong) / n, 100 * exp_all_wrong))
    print("из них хотя бы две системы назвали ОДИН И ТОТ ЖЕ «неверный» ответ: %d" % len(agree))
    errs = sum(1 for i in idx for s in systems if pred[s][i] != bench[i]["ответ"])
    in_core = sum(1 for i in all_wrong for s in systems)
    print("доля всех ошибок трёх систем, которая приходится на вопросы «ошиблись все»: %.0f%%" % (100 * in_core / errs))
    print("-" * 100)
    for i, top, cnt in agree[:14]:
        r = bench[i]
        print("ВОПРОС: %s\n   эталон: %s — %s\n   системы (%d из 3): %s — %s" % (
            r["вопрос"], r["ответ"], name.get(r["ответ"], "?")[:90], cnt, top, name.get(top, "?")[:90]))
    out[dom] = {"n": n, "точность": acc, "гистограмма": hist, "все_ошиблись": len(all_wrong), "ожидалось": exp_all_wrong,
                "согласны_не_с_эталоном": len(agree)}
json.dump(out, open(S + "/диаг.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
