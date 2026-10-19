# -*- coding: utf-8 -*-
"""ПОСЛЕ замера, не предсказывалось: как меняется флагманский счёт при другом пороге ответа схемы (0,1 … 0,7).
v8 по умолчанию осторожна (порог 0,5); здесь видно, сколько верных и неверных ответов она даёт при пороге, когда отвечает
примерно столько же раз, сколько v6. Пишет результаты/порог.json."""
import json
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as О  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ПОРОГИ = [0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]


def решение(rec, θ, θ_обл=0.5):
    c = rec["кандидаты"][0] if rec["кандидаты"] else None
    if c and c["p"] >= θ:
        _, обл, ид = c["ответ"].split(":", 2)
        return {"область": обл, "id": ид}
    обл = {k.split(":", 1)[1]: 1 / (1 + math.exp(-v)) for k, v in rec["шина"].items() if k.startswith("область:")}
    обл = {o: q for o, q in обл.items() if q >= θ_обл}
    if обл:
        return {"область": max(обл, key=lambda o: (обл[o], o)), "id": ""}
    return {"область": "вне", "id": ""}


def main(варианты=("основная", "один_проход", "без_выходных", "монолит"), зерно=1):
    Н = О.наборы()
    rows = Н["флагманский_600"]
    M = О.оценка_флагманов()
    items = M.срезы(rows)["всё · основная разметка"]
    res = {}
    for v in варианты:
        k, _ = О.система(v, зерно, проверять_язык=False)
        recs = {r["ключ"]: k.спросить(r["текст"])[1] for r in rows}
        res[v] = {}
        for θ in ПОРОГИ:
            ans = {key: dict(решение(rec, θ), ключ=key) for key, rec in recs.items()}
            c = M.счёт(items, ans)
            res[v][str(θ)] = {"ответов": c["ответов"], "уверенных_ошибок": c["ошибок"], "здоровье_статья": "%d/%d" % (c["зд_ok"], c["зд_n"]),
                              "право_тема": "%d/%d" % (c["пр_ok"], c["пр_n"]), "область_верна": "%d/%d" % (c["область"], c["вопросов"]),
                              "вне→вне": "%d/%d" % (c["вне_ok"], c["вне_n"]), "верных_ответов": c["зд_ok"] + c["пр_ok"]}
        print(v, json.dumps(res[v], ensure_ascii=False), flush=True)
    for name in ("nnl_В2б", "nnl_Д"):
        ans = {a["ключ"]: a for a in О.jl(os.path.join(О.БАЗА, "бенчмарки", "флагманы", "ответы", name + ".jsonl"))}
        c = M.счёт(items, ans)
        res["v6_" + name[4:]] = {"ответов": c["ответов"], "уверенных_ошибок": c["ошибок"], "здоровье_статья": "%d/%d" % (c["зд_ok"], c["зд_n"]),
                                 "право_тема": "%d/%d" % (c["пр_ok"], c["пр_n"]), "верных_ответов": c["зд_ok"] + c["пр_ok"],
                                 "область_верна": "%d/%d" % (c["область"], c["вопросов"]), "вне→вне": "%d/%d" % (c["вне_ok"], c["вне_n"])}
        print("v6_" + name[4:], json.dumps(res["v6_" + name[4:]], ensure_ascii=False))
    json.dump(res, open(os.path.join(О.V8, "результаты", "порог.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
