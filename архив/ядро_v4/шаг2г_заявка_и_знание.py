# -*- coding: utf-8 -*-
"""Шаг 2г: блоки «заявка» + «знание». Вставка, выключение знания, полное снятие. Пишет результаты/шаг2г.json.
Запуск: python шаг2г_заявка_и_знание.py"""
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
SPLIT, OLD = os.path.join(V4, "блоки_раздел"), os.path.join(V4, "блоки_ф2к")
DOM = ("здоровье", "право", "команды")


def kernel(*paths):
    k = Kernel(TYPES, ARCH)
    for p in paths:
        ok, msg = k.attach(p)
        assert ok, (p, msg)
    return k


def split_paths(areas):
    return [os.path.join(SPLIT, a + s) for a in areas for s in (".заявка", "")]


def run(k, bench):
    return [k.ask(r["вопрос"])[1] for r in bench]


def key(rec):
    return json.dumps(rec["ответ"], sort_keys=True, ensure_ascii=False)


def score(bench, recs):
    t = {d: {"вопросов": 0, "верно": 0, "не_знаю": 0, "в_чужой": 0} for d in DOM}
    for r, rec in zip(bench, recs):
        s = t[r["область"]]
        s["вопросов"] += 1
        a = rec["ответ"]
        if a == NOT_KNOWN:
            s["не_знаю"] += 1
        elif a["область"] != r["область"]:
            s["в_чужой"] += 1
        elif a["id"] == r["ответ"]:
            s["верно"] += 1
    for s in t.values():
        s["доля_верных"] = round(s["верно"] / s["вопросов"], 4)
    return t


def main():
    with open(os.path.join(V4, "измеритель", "шаг2.jsonl"), encoding="utf-8") as f:
        bench = [json.loads(l) for l in f if l.strip()]
    hashes = {d: sha256_file(os.path.join(SPLIT, d, "веса.npz")) for d in os.listdir(SPLIT)}
    out = {}
    r_old = run(kernel(*[os.path.join(OLD, a) for a in DOM]), bench)
    k_all = kernel(*split_paths(DOM))
    r_all = run(k_all, bench)
    same = sum(key(a) == key(b) for a, b in zip(r_old, r_all))
    out["совпало_с_2в"] = "%d/%d" % (same, len(bench))
    out["все_на_месте"] = score(bench, r_all)
    out["чисел"] = k_all.total_numbers()
    print("все блоки (6): совпало с 2в %d/%d; " % (same, len(bench)),
          {d: (s["доля_верных"], s["не_знаю"], s["в_чужой"]) for d, s in out["все_на_месте"].items()})

    k = kernel(*split_paths(("здоровье", "право")))
    before = run(k, bench)
    ok1, _, rep1 = k.attach_checked(os.path.join(SPLIT, "команды.заявка"))
    ok2, _, rep2 = k.attach_checked(os.path.join(SPLIT, "команды"))
    after = run(k, bench)
    idx = [i for i, r in enumerate(bench) if r["область"] in ("здоровье", "право")]
    ch = sum(key(before[i]) != key(after[i]) for i in idx)
    out["вставка_команд"] = {"изменилось_здоровье_право": "%d/%d" % (ch, len(idx)), "контроль_ядра": {
        n: {k2: v for k2, v in r.items() if k2 != "ответы"} for n, r in rep2.items()}}
    print("вставка «команд» (заявка+знание): изменилось ответов здоровья и права %d из %d" % (ch, len(idx)))

    for mode in ("выключено_знание", "снято_всё"):
        res = {}
        for d in DOM:
            if mode == "выключено_знание":
                paths = [p for p in split_paths(DOM) if os.path.basename(p) != d]
            else:
                paths = split_paths([x for x in DOM if x != d])
            recs = run(kernel(*paths), bench)
            own = [(r, rec) for r, rec in zip(bench, recs) if r["область"] == d]
            other_idx = [i for i, r in enumerate(bench) if r["область"] != d]
            res[d] = {"свои_не_знаю": "%d/%d" % (sum(rec["ответ"] == NOT_KNOWN for _, rec in own), len(own)),
                      "свои_в_чужой_блок": sum(1 for _, rec in own if rec["ответ"] != NOT_KNOWN),
                      "у_других_изменилось": "%d/%d" % (sum(key(recs[i]) != key(r_all[i]) for i in other_idx), len(other_idx)),
                      "пример_отказа": next((rec.get("отказ") for _, rec in own if rec["ответ"] == NOT_KNOWN), None)}
            print("%-17s %-9s: свои «не знаю» %s, свои к чужому блоку %d, у других изменилось %s" % (
                mode, d, res[d]["свои_не_знаю"], res[d]["свои_в_чужой_блок"], res[d]["у_других_изменилось"]))
        out[mode] = res
    out["пример_отказа_при_выключенном_знании"] = out["выключено_знание"]["здоровье"]["пример_отказа"]
    out["файлы_весов_не_менялись"] = all(sha256_file(os.path.join(SPLIT, d, "веса.npz")) == h for d, h in hashes.items())
    with open(os.path.join(V4, "результаты", "шаг2г.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("отказ ядра при выключенном знании:", out["пример_отказа_при_выключенном_знании"])
    print("файлы весов не менялись:", out["файлы_весов_не_менялись"], "| чисел:", out["чисел"])


if __name__ == "__main__":
    main()
