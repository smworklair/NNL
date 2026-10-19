# -*- coding: utf-8 -*-
"""Целостность v6 (система В2): 30 случайных снятий/возвратов блоков. После каждого снятия на 80 случайных вопросах:
  «путь цел»  — вопрос, путь которого не шёл через снятый блок, получил тот же ответ, что и до всех операций;
  «нет знания» — снято знание области, а её заявка на месте: вопрос этой области получил «не знаю»;
  «чужая область» — снята заявка: ответ не из её области.
После возврата блока — все ответы как в начале. В конце — sha256 всех файлов блоков и типов не изменились.
Запуск: python тест_целостности.py"""
import hashlib
import json
import os
import random
import sys

sys.dont_write_bytecode = True
V6 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V6)
from ядро import NOT_KNOWN, Kernel  # noqa: E402
from замер import SYS, jl  # noqa: E402

B = os.path.join(V6, "блоки")
SYSNAME = sys.argv[1] if len(sys.argv) > 1 else "В2"
NAMES = SYS[SYSNAME]


def hashes():
    h = {}
    for root in [os.path.join(B, n) for n in NAMES] + [os.path.join(V6, "типы")]:
        for dp, _, fs in os.walk(root):
            for f in fs:
                p = os.path.join(dp, f)
                h[os.path.relpath(p, V6)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return h


def key(a):
    return json.dumps(a, ensure_ascii=False, sort_keys=True)


def main():
    h0 = hashes()
    k = Kernel(os.path.join(V6, "типы"), os.path.join(V6, "архитектуры"))
    for n in NAMES:
        assert k.attach(os.path.join(B, n))[0]
    qs = [r["вопрос"] for r in jl(r"C:\ЯДРО-ОПЫТ\бенчмарки\bench\bench.jsonl")] + \
         [r["вопрос"] for r in jl(os.path.join(V6, "реальные", "разметка_свежие.jsonl"))] + \
         [r["текст"] for r in jl(os.path.join(V6, "реальные", "отрицания.jsonl"))]
    base = {}
    for q in qs:
        a, rec = k.ask(q)
        base[q] = (key(a), rec["путь"], None if a == NOT_KNOWN else a["область"])
    area = {n: k.blocks[n].passport["область"] for n in NAMES}
    is_claim = {n: bool(k.blocks[n].passport.get("заявка")) for n in NAMES}
    rnd = random.Random(6)
    c = {"путь_цел": [0, 0], "нет_знания": [0, 0], "чужая_область": [0, 0], "после_возврата": [0, 0]}
    bad = []
    for step in range(30):
        n = rnd.choice(NAMES)
        k.detach(n)
        for q in rnd.sample(qs, 80):
            a, rec = k.ask(q)
            ka, path, ar = base[q]
            if n not in path:
                c["путь_цел"][1] += 1
                ok = key(a) == ka
                c["путь_цел"][0] += ok
            elif not is_claim[n]:
                c["нет_знания"][1] += 1
                ok = a == NOT_KNOWN
                c["нет_знания"][0] += ok
            else:
                c["чужая_область"][1] += 1
                ok = a == NOT_KNOWN or a["область"] != area[n] or any(area[m] == area[n] and is_claim[m] for m in k.blocks)
                c["чужая_область"][0] += ok
            if not ok:
                bad.append({"шаг": step, "снят": n, "вопрос": q[:80], "ответ": key(a)[:120]})
        ok, msg = k.attach(os.path.join(B, n))
        assert ok, msg
        for q in rnd.sample(qs, 80):
            c["после_возврата"][1] += 1
            c["после_возврата"][0] += key(k.ask(q)[0]) == base[q][0]
    full = sum(key(k.ask(q)[0]) == base[q][0] for q in qs)
    h1 = hashes()
    out = {"система": SYSNAME, "блоки": NAMES, "проверок": {x: "%d/%d" % tuple(v) for x, v in c.items()}, "нарушений": len(bad), "примеры_нарушений": bad[:10],
           "в_конце_все_ответы_как_в_начале": "%d/%d" % (full, len(qs)),
           "файлов_изменено": sum(h0[p] != h1.get(p) for p in h0)}
    json.dump(out, open(os.path.join(V6, "результаты", "целостность_%s.json" % SYSNAME), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
