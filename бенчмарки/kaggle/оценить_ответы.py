# -*- coding: utf-8 -*-
"""Считает ответы моделей на 50 вопросов (вопросы_для_моделей.txt) по разметке Muse Spark — тем же способом, что и у нашей модели.
Ответы каждой модели — в папке ответы_моделей\<имя модели>.txt (как модель их выдала, 50 строк JSON).
Запуск: python оценить_ответы.py"""
import glob, json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
Q = json.load(open(os.path.join(HERE, "nnl_svezhie3.json"), encoding="utf-8"))["questions"][:50]
def score(get):
    a = s = n = 0
    for q in Q:
        r = get(q) or {}
        got = (r.get("область") or "вне").strip()
        a += q["area"] == "спорно" or got == q["area"]
        if q["area"] in ("здоровье", "право") and q["answers"]:
            n += 1; s += got == q["area"] and str(r.get("id", "")).strip() in q["answers"]
    return a, s, n
for p in sorted(glob.glob(os.path.join(HERE, "ответы_моделей", "*.txt"))):
    rows = {}
    for m in re.finditer(r"\{[^{}]*\}", open(p, encoding="utf-8").read()):
        try:
            r = json.loads(m.group(0)); rows[int(r["i"])] = r
        except Exception:
            pass
    a, s, n = score(lambda q: rows.get(q["i"]))
    print("%-30s область %2d/50 | статья/тема %2d/%d | разобрано строк %d" % (os.path.basename(p)[:-4], a, s, n, len(rows)))
