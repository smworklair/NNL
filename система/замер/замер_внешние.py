# -*- coding: utf-8 -*-
"""Замер основная.з1 vs основная_внешние.з1 на чистых наборах + фразы (с оговоркой: фразы видены новой системой).
Чистые (не были в обучении обеих систем): проверка 200, свежие3 200, свежие4 200, флагманские 600, bench 461.
Пишет v8/результаты/замер_внешние.з1.json. Запуск: python замер/замер_внешние.py"""
import collections
import json
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as О  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def живые_внешние(k, вопросы, разметки):
    """Метрика как О.живые, но формат внешних: вопросы {i,текст}, разметка {i,область,ответы}."""
    txt = {r["i"]: r["текст"] for r in вопросы}
    c = collections.Counter()
    for r in разметки:
        t = txt[r["i"]]
        a, _ = k.спросить(t)
        got = О.область(a)
        grp = r["область"]
        c["n"] += 1
        c["обл"] += got == grp
        c[grp, "n"] += 1
        c[grp, "обл"] += got == grp
        if r["ответы"] and grp in ("здоровье", "право"):
            c[grp, "сотв"] += 1
            c[grp, "отв"] += got == grp and О.ид(a) in r["ответы"]
        if О.ид(a):
            c["ответов"] += 1
            wrong = grp == "вне" or (grp in ("здоровье", "право") and not (got == grp and (not r["ответы"] or О.ид(a) in r["ответы"])))
            c["ошибок"] += wrong
    out = {"область_верна": "%d/%d" % (c["обл"], c["n"]), "ответов": c["ответов"], "уверенных_ошибок": c["ошибок"]}
    for g in ("здоровье", "право", "вне", "спорно"):
        if c[g, "n"]:
            out[g] = {"всего": c[g, "n"], "область_верна": c[g, "обл"]}
            if c[g, "сотв"]:
                out[g]["верный_ответ"] = "%d/%d" % (c[g, "отв"], c[g, "сотв"])
    return out


def main():
    t0 = time.time()
    ВН = os.path.join(О.БАЗА, "внешние")
    ext = {}
    for name, qf, rfs in (("проверка", "проверка_вопросы.json", ["разметка_проверка.jsonl", "cowork_проверка.jsonl"]),
                          ("свежие3", "свежие3_вопросы.json", ["разметка_свежие3.jsonl"]),
                          ("свежие4", "свежие4_вопросы.json", ["разметка_свежие4.jsonl"])):
        q = json.load(open(os.path.join(ВН, qf), encoding="utf-8"))
        ext[name] = [(qf, q, rf, О.jl(os.path.join(ВН, rf))) for rf in rfs]
    Н = О.наборы()
    res = {"наборы": {k: len(v) for k, v in Н.items()}, "внешние": {}}
    for v in ("основная", "основная_внешние"):
        k, _ = О.система(v, 1)
        r = {}
        r["общий_тест"] = О.общий_тест(k, Н["общий_тест"])
        r["отрицания_210"] = О.отрицания(k, Н["отрицания_210"])
        r["фразы_150*"] = О.фразы(k, Н["фразы_150"])
        for name, groups in ext.items():
            for qf, q, rf, разм in groups:
                r["%s/%s" % (name, rf)] = живые_внешние(k, q, разм)
        отв = О.ответы_флагманского(k, Н["флагманский_600"])
        M = О.оценка_флагманов()
        sl = M.срезы(Н["флагманский_600"])
        ans = {a["ключ"]: a for a in отв}
        r["флагманский_600_основная"] = M.счёт(sl["всё · основная разметка"], ans)
        res["внешние" if False else "системы_" + v] = r
        print(v, json.dumps({kk: vv for kk, vv in r.items() if kk in ("общий_тест",)}, ensure_ascii=False)[:300], "%.0f с" % (time.time() - t0), flush=True)
    out = os.path.join(О.V8, "результаты", "замер_внешние.з1.json")
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("записано", out, "%.0f с" % (time.time() - t0))


if __name__ == "__main__":
    main()
