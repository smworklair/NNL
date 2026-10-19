# -*- coding: utf-8 -*-
"""Замер на dev (только dev: lay/учитель dev, lex dev, 15 % живых пулов, фон dev) — для выбора и для предсказания.
Проверочные наборы не трогаются. Запуск: python замер/dev.py [варианты] [зерно]"""
import collections
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as О  # noqa: E402
from обучение import данные as D  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main(варианты, зерно=1):
    _, dev, _ = D.собрать(seed=1)
    res = {}
    for v in варианты:
        k, _ = О.система(v, зерно, проверять_язык=False)
        c = collections.Counter()
        for r in dev:
            a, rec = k.спросить(r["текст"])
            g = r["группа"]
            obl = "здоровье" if r["понятия"]["область:здоровье"] == 1 else ("право" if r["понятия"]["область:право"] == 1 else "вне")
            top = rec["кандидаты"][0]["ответ"] if rec.get("кандидаты") else ""
            c[g, "n"] += 1
            if r["ответы"]:
                c[g, "с_ответом"] += 1
                c[g, "первый"] += top in r["ответы"]
                c[g, "верный_ответ"] += a != О.НЕ_ЗНАЮ and a["вид"] == "ответ" and "ответ:%s:%s" % (a["область"], a["id"]) in r["ответы"]
            c[g, "область_верна"] += О.область(a) == obl
            c[g, "ответов"] += bool(О.ид(a))
            if О.ид(a) and not (r["ответы"] and "ответ:%s:%s" % (a["область"], a["id"]) in r["ответы"]):
                c[g, "ошибок"] += 1
            if obl == "вне":
                c[g, "вне_n"] += 1
                c[g, "вне_ok"] += О.область(a) == "вне"
        out = {}
        for g in ("здоровье", "право", "живые", "фон"):
            n = c[g, "n"]
            d = {"n": n, "область_верна": round(c[g, "область_верна"] / n, 3), "ответов": c[g, "ответов"], "ошибок": c[g, "ошибок"]}
            if c[g, "с_ответом"]:
                d["первый_ответ_верен"] = round(c[g, "первый"] / c[g, "с_ответом"], 3)
                d["верный_ответ_при_пороге"] = round(c[g, "верный_ответ"] / c[g, "с_ответом"], 3)
            if c[g, "вне_n"]:
                d["вне→вне"] = round(c[g, "вне_ok"] / c[g, "вне_n"], 3)
            out[g] = d
        res[v] = out
        print(v, json.dumps(out, ensure_ascii=False), flush=True)
    return res


if __name__ == "__main__":
    a = sys.argv[1:]
    r = main(a[0].split(",") if a else ["основная", "один_проход", "без_выходных", "монолит"], int(a[1]) if len(a) > 1 else 1)
    p = os.path.join(О.V8, "результаты", "dev.json")
    old = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    old.update({"%s.з%s" % (k, a[1] if len(a) > 1 else 1): v for k, v in r.items()})
    json.dump(old, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
