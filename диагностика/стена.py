# -*- coding: utf-8 -*-
"""«Стена»: вопросы общего теста, на которых ошиблись все три системы разного устройства. Пишет стена.md.
Здоровье: TINY 1.6 (сеть приложения), блок знаний v4 (мешок слов), цепочка v3 (разбор → блок).
Право: блок знаний v4, цепочка v3, NNL v6 (система Д). Ответы систем — v4.json, v6.json (диаг_v4.py, диаг_v6.py)."""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
D = os.path.dirname(os.path.abspath(__file__))
bench = [json.loads(l) for l in open(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl", encoding="utf-8") if l.strip()]
pred = {}
for f in ("v4.json", "v6.json"):
    pred.update(json.load(open(os.path.join(D, f), encoding="utf-8")))
sp = json.load(open(r"C:\ЯДРО-ОПЫТ\внешние\справочник.json", encoding="utf-8"))
name = {x["id"]: x["название"] for x in sp["статьи_болезней"] + sp["правовые_темы"]}
TRIO = {"здоровье": ["TINY_1.6", "v4_знание", "v3_цепочка"], "право": ["v4_знание", "v3_цепочка", "NNL_Д"]}
md = ["# Стена: вопросы, на которых ошиблись все три системы разного устройства", "",
      "Если бы ошибки систем были независимы, таких вопросов было бы 1,5 % (здоровье) и 2,2 % (право). На деле — 15,4 % и 12,5 %.",
      "Пометьте у каждого вопроса одно: **эталон верен** / **системы правы** / **подходят оба** / **по тексту не ответить**.", ""]
n = 0
for dom, systems in TRIO.items():
    md += ["## %s" % dom, ""]
    for i, r in enumerate(bench):
        if r["область"] != dom or any(pred[s][i] == r["ответ"] for s in systems):
            continue
        n += 1
        md.append("**%d. %s**  " % (n, r["вопрос"]))
        md.append("эталон: `%s` — %s  " % (r["ответ"], name.get(r["ответ"], "?")))
        for s in systems:
            p = pred[s][i]
            md.append("%s: `%s` — %s  " % (s, p, name.get(p, "не ответила") if p else "не ответила"))
        md.append("вердикт: ______")
        md.append("")
open(os.path.join(D, "стена.md"), "w", encoding="utf-8").write("\n".join(md))
print("вопросов в стене:", n)
