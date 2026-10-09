# -*- coding: utf-8 -*-
"""Шаг 3: блок задач отдельно (вне ядра). Доля верных итогов на проверочных наборах; без калькулятора — ещё доля
решений, где все шаги <<…=…>> посчитаны верно (их пропустит проверка типа общие:Ответ).
Запуск: python шаг3_оценка_решателя.py <папка блока> [--без-калькулятора] [--n 300] [--наборы ...]"""
import argparse
import json
import os
import sys
import time

V4 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V4)
sys.path.insert(0, os.path.join(V4, "архитектуры"))
sys.path.insert(0, os.path.join(V4, "типы", "общие"))
import решатель as R  # noqa: E402
import решатель2 as R2  # noqa: E402
import проверки as CHK  # noqa: E402

SETS = ["тест_ген2_знакомые", "тест_ген2_новые_фразы", "тест_ген_знакомые", "тест_ген_новые", "тест_gsm8k_en", "тест_gsm8k_ru", "тест_mgsm_en", "тест_mgsm_ru"]


def same_number(a, b):
    try:
        return a is not None and abs(float(a) - float(b)) < 1e-6
    except ValueError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("блок")
    ap.add_argument("--без-калькулятора", action="store_true")
    ap.add_argument("--n", type=int, default=0, help="сколько задач с начала каждого набора (0 — все)")
    ap.add_argument("--наборы", nargs="*", default=SETS)
    a = ap.parse_args()
    bdir = os.path.join(V4, a.блок)
    ps = json.load(open(os.path.join(bdir, "паспорт.json"), encoding="utf-8"))
    ps["настройки"]["калькулятор"] = not a.без_калькулятора
    M = R2 if ps["архитектура"] == "решатель2" else R
    obj = M.load(os.path.join(bdir, "веса.npz"), ps, None)
    res, examples = {}, {}
    for name in a.наборы:
        rows = [json.loads(l) for l in open(os.path.join(V4, "задачи", "наборы", name + ".jsonl"), encoding="utf-8")]
        if a.n and a.n < len(rows):   # равномерно по набору (в наборах генератора сначала идут ru, потом en)
            step = len(rows) / a.n
            rows = [rows[int(i * step)] for i in range(a.n)]
        t0, ok, ok_steps, by_lang = time.time(), 0, 0, {}
        for r in rows:
            text, final = M.solve(obj, r["question"])[:2]
            good = same_number(final, r["итог"])
            ok += good
            ok_steps += not [s for s in CHK.steps(text) if not s[2]]
            lg = by_lang.setdefault(r.get("вид", r["язык"]) if name.startswith("тест_ген") else r["язык"], [0, 0])
            lg[0] += 1
            lg[1] += good
            if len(examples.setdefault(name, [])) < 3:
                examples[name].append({"вопрос": r["question"][:200], "решение": text[:400], "итог": final, "верный": r["итог"]})
        res[name] = {"задач": len(rows), "верно": ok, "доля": round(ok / len(rows), 4),
                     "все_шаги_верны": round(ok_steps / len(rows), 4), "по_видам": {k: "%d/%d" % (v[1], v[0]) for k, v in sorted(by_lang.items())},
                     "сек_на_задачу": round((time.time() - t0) / len(rows), 2)}
        print("%-20s %s: верно %d/%d = %.3f; все шаги верны %.3f; %s" % (
            name, "калькулятор" if not a.без_калькулятора else "без калькулятора", ok, len(rows), ok / len(rows), ok_steps / len(rows),
            res[name]["по_видам"]), flush=True)
    tag = "" if len(a.наборы) == len(SETS) else "_" + "+".join(a.наборы)
    out = os.path.join(V4, "результаты", "шаг3_%s_%s%s%s.json" % (os.path.basename(bdir), "без_кальк" if a.без_калькулятора else "кальк", "_n%d" % a.n if a.n else "", tag))
    json.dump({"блок": a.блок, "чисел": ps["веса"]["чисел"], "результаты": res, "примеры": examples}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("записано", out)


if __name__ == "__main__":
    main()
