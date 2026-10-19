# -*- coding: utf-8 -*-
"""Шаг 2: блоки нового образца (заявка «моё/фон») — здоровье и право, затем вставка «команд» без переобучения первых двух.
Измеритель: измеритель/шаг2.jsonl (общий bench 461 + 1000 команд MASSIVE test). Пишет результаты/шаг2.json.
Запуск: python шаг2_вставка_области.py"""
import json
import os
import sys

V4 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V4)
from ядро import NOT_KNOWN, Kernel  # noqa: E402
from ядро.схема import sha256_file  # noqa: E402

TYPES, ARCH = os.path.join(V4, "типы"), os.path.join(V4, "архитектуры")
BLOCKS = os.path.join(V4, sys.argv[1] if len(sys.argv) > 1 else "блоки")
RESULT = sys.argv[2] if len(sys.argv) > 2 else "шаг2.json"
DOM = ("здоровье", "право", "команды")


def run(k, bench):
    return [k.ask(r["вопрос"])[1] for r in bench]


def score(bench, recs):
    t = {d: {"вопросов": 0, "верно": 0, "не_знаю": 0, "в_чужой_блок": {}} for d in DOM}
    for r, rec in zip(bench, recs):
        s = t[r["область"]]
        s["вопросов"] += 1
        a = rec["ответ"]
        if a == NOT_KNOWN:
            s["не_знаю"] += 1
        elif a["область"] != r["область"]:
            s["в_чужой_блок"][a["область"]] = s["в_чужой_блок"].get(a["область"], 0) + 1
        elif a["id"] == r["ответ"]:
            s["верно"] += 1
    for s in t.values():
        s["доля_верных"] = round(s["верно"] / s["вопросов"], 4)
    hl = t["здоровье"]["верно"] + t["право"]["верно"]
    t["здоровье+право"] = {"доля_верных": round(hl / (t["здоровье"]["вопросов"] + t["право"]["вопросов"]), 4)}
    return t


def changed(bench, a, b, doms):
    idx = [i for i, r in enumerate(bench) if r["область"] in doms]
    n = sum(json.dumps(a[i]["ответ"], sort_keys=True) != json.dumps(b[i]["ответ"], sort_keys=True) for i in idx)
    return n, len(idx)


def line(s):
    return " | ".join("%s %.3f (не знаю %d, в чужой %s)" % (d, s[d]["доля_верных"], s[d]["не_знаю"], s[d]["в_чужой_блок"] or 0) for d in DOM)


def main():
    with open(os.path.join(V4, "измеритель", "шаг2.jsonl"), encoding="utf-8") as f:
        bench = [json.loads(l) for l in f if l.strip()]
    hashes = {d: sha256_file(os.path.join(BLOCKS, d, "веса.npz")) for d in DOM}
    out = {}
    k = Kernel(TYPES, ARCH)
    for d in ("здоровье", "право"):
        ok, msg = k.attach(os.path.join(BLOCKS, d))
        assert ok, msg
    before = run(k, bench)
    s1 = score(bench, before)
    out["до_вставки"] = s1
    print("ДО вставки (здоровье, право):", line(s1))

    ok, msg, rep = k.attach_checked(os.path.join(BLOCKS, "команды"))
    assert ok, msg
    out["контроль_ядра_при_вставке"] = rep
    print("\nконтроль ядра при вставке «команд»:", {n: {k2: v for k2, v in r.items() if k2 != "ответы"} for n, r in rep.items()})
    after = run(k, bench)
    s2 = score(bench, after)
    out["после_вставки"] = s2
    n_ch, n_hl = changed(bench, before, after, ("здоровье", "право"))
    out["изменилось_ответов_здоровья_и_права"] = "%d/%d" % (n_ch, n_hl)
    out["изменилось_доля"] = round(n_ch / n_hl, 4)
    print("ПОСЛЕ вставки:", line(s2))
    print("изменилось ответов здоровья и права: %d из %d (%.1f %%)" % (n_ch, n_hl, 100 * n_ch / n_hl))

    # снятие: каждого блока по очереди
    rm = {}
    for d in DOM:
        kk = Kernel(TYPES, ARCH)
        for x in DOM:
            kk.attach(os.path.join(BLOCKS, x))
        kk.detach(d)
        recs = run(kk, bench)
        sc = score(bench, recs)
        others = [x for x in DOM if x != d]
        n_o, tot_o = changed(bench, after, recs, others)
        own = [rec for r, rec in zip(bench, recs) if r["область"] == d]
        rm[d] = {"ответов_из_снятой_области": sum(1 for rec in recs if rec["ответ"] != NOT_KNOWN and rec["ответ"]["область"] == d),
                 "вопросы_снятой_области_не_знаю": "%d/%d" % (sum(rec["ответ"] == NOT_KNOWN for rec in own), len(own)),
                 "вопросы_снятой_области_ушли_в": sc[d]["в_чужой_блок"],
                 "у_остальных_изменилось": "%d/%d" % (n_o, tot_o)}
        print("снят «%s»: его вопросы — «не знаю» %s, ушли в %s; у остальных изменилось %s" % (
            d, rm[d]["вопросы_снятой_области_не_знаю"], rm[d]["вопросы_снятой_области_ушли_в"] or "никуда", rm[d]["у_остальных_изменилось"]))
    out["снятие"] = rm
    # примеры ошибок маршрута
    ex = []
    for r, rec in zip(bench, after):
        a = rec["ответ"]
        if a != NOT_KNOWN and a["область"] != r["область"] and len(ex) < 12:
            ex.append({"вопрос": r["вопрос"][:140], "область": r["область"], "ушёл_в": a["область"], "заявки": rec.get("заявки")})
    out["примеры_чужого_блока"] = ex
    out["файлы_весов_не_менялись"] = all(sha256_file(os.path.join(BLOCKS, d, "веса.npz")) == hashes[d] for d in DOM)
    out["чисел"] = k.total_numbers()
    os.makedirs(os.path.join(V4, "результаты"), exist_ok=True)
    with open(os.path.join(V4, "результаты", RESULT), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nпримеры чужого блока:")
    for e in ex[:8]:
        print("  ", e)
    print("файлы весов не менялись:", out["файлы_весов_не_менялись"], "| чисел в системе:", out["чисел"])


if __name__ == "__main__":
    main()
