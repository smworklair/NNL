# -*- coding: utf-8 -*-
"""Шаг 4: блок задач (заявка + решатель) в одном ядре с военкоматом (здоровье и право — заявка + знание).
Проверки: вставка задач не меняет ответы военкомата; задачи решаются через ядро; вынули решатель — задачи «не знаю»;
вынули всё про задачи — куда уходят задачи; без калькулятора ядро отказывает на неверной арифметике.
Запуск: python шаг4_задачи_в_ядре.py <папка решателя> [--n 200] [--с-командами]"""
import argparse
import json
import os
import shutil
import sys
import time

V4 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V4)
from ядро import NOT_KNOWN, Kernel  # noqa: E402
from ядро.схема import sha256_file  # noqa: E402

TYPES, ARCH = os.path.join(V4, "типы"), os.path.join(V4, "архитектуры")
SPLIT = os.path.join(V4, "блоки_раздел")
CLAIM = os.path.join(V4, "блоки_задачи", "задачи.заявка")


def mil(with_commands):
    areas = ["здоровье", "право"] + (["команды"] if with_commands else [])
    return [os.path.join(SPLIT, a + s) for a in areas for s in (".заявка", "")]


def kernel(paths):
    k = Kernel(TYPES, ARCH)
    for p in paths:
        ok, msg = k.attach(p)
        assert ok, (p, msg)
    return k


def num_eq(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("решатель")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--с-командами", action="store_true")
    a = ap.parse_args()
    solver = os.path.join(V4, a.решатель)
    bench = [json.loads(l) for l in open(os.path.join(V4, "измеритель", "шаг2.jsonl"), encoding="utf-8")]
    if not a.с_командами:
        bench = [r for r in bench if r["область"] != "команды"]
    tasks = []
    for name in ("тест_ген2_знакомые", "тест_ген2_новые_фразы", "тест_ген_знакомые", "тест_ген_новые", "тест_gsm8k_en", "тест_gsm8k_ru", "тест_mgsm_en", "тест_mgsm_ru"):
        rows = [json.loads(l) for l in open(os.path.join(V4, "задачи", "наборы", name + ".jsonl"), encoding="utf-8")]
        # равномерно по набору (в знакомых/новых — смесь ru и en)
        step = max(1, len(rows) // a.n)
        tasks += [dict(r, набор=name) for r in rows[::step][:a.n]]
    hashes = {p: sha256_file(os.path.join(p, "веса.npz")) for p in mil(a.с_командами) + [CLAIM, solver]}
    out = {"решатель": a.решатель, "задач_в_проверке": len(tasks)}

    k0 = kernel(mil(a.с_командами))
    m0 = [k0.ask(r["вопрос"])[1]["ответ"] for r in bench]
    k = kernel(mil(a.с_командами))
    ok, msg, rep1 = k.attach_checked(CLAIM)
    ok2, msg2, rep2 = k.attach_checked(solver)
    assert ok and ok2, (msg, msg2)
    out["чисел_в_системе"] = k.total_numbers()
    m1 = [k.ask(r["вопрос"])[1]["ответ"] for r in bench]
    ch = sum(json.dumps(x, sort_keys=True) != json.dumps(y, sort_keys=True) for x, y in zip(m0, m1))
    to_tasks = sum(1 for x in m1 if x != NOT_KNOWN and x.get("область") == "задачи")
    out["вставка_задач"] = {"изменилось_ответов_военкомата": "%d/%d" % (ch, len(bench)), "ушли_в_задачи": to_tasks,
                            "контроль_ядра": {n: {kk: v for kk, v in r.items() if kk != "ответы"} for n, r in rep2.items()}}
    print("вставка задач: изменилось ответов прочих областей %d из %d (ушли в задачи: %d); чисел в системе %d" % (ch, len(bench), to_tasks, out["чисел_в_системе"]), flush=True)

    def run_tasks(kk):
        res, t0 = {}, time.time()
        recs = []
        for r in tasks:
            ans, rec = kk.ask(r["question"])
            s = res.setdefault(r["набор"], {"задач": 0, "верно": 0, "не_знаю": 0, "в_чужую_область": 0, "отказ_проверки_типа": 0})
            s["задач"] += 1
            if ans == NOT_KNOWN:
                s["не_знаю"] += 1
                s["отказ_проверки_типа"] += "неверно посчитаны" in (rec.get("отказ") or "")
            elif ans.get("область") != "задачи":
                s["в_чужую_область"] += 1
            elif num_eq(ans.get("итог"), r["итог"]):
                s["верно"] += 1
            recs.append(rec)
        for s in res.values():
            s["доля"] = round(s["верно"] / s["задач"], 4)
        return res, recs, round((time.time() - t0) / len(tasks), 2)

    res, recs, spt = run_tasks(k)
    out["задачи_через_ядро"] = res
    out["сек_на_задачу"] = spt
    print("задачи через ядро (калькулятор):", {n: (s["доля"], s["не_знаю"], s["в_чужую_область"]) for n, s in res.items()}, flush=True)
    out["пример_следа"] = recs[0]

    k.detach(os.path.basename(solver) if False else json.load(open(os.path.join(solver, "паспорт.json"), encoding="utf-8"))["имя"])
    res_off, _, _ = run_tasks(k)
    m2 = [k.ask(r["вопрос"])[1]["ответ"] for r in bench]
    ch2 = sum(json.dumps(x, sort_keys=True) != json.dumps(y, sort_keys=True) for x, y in zip(m1, m2))
    nk = sum(s["не_знаю"] for s in res_off.values())
    out["вынут_решатель"] = {"задачи_не_знаю": "%d/%d" % (nk, len(tasks)), "у_прочих_изменилось": "%d/%d" % (ch2, len(bench)), "по_наборам": res_off}
    print("вынут решатель: задачи «не знаю» %d из %d; у прочих изменилось %d из %d" % (nk, len(tasks), ch2, len(bench)), flush=True)

    k.detach("задачи.заявка")
    res_all, _, _ = run_tasks(k)
    leak = sum(s["в_чужую_область"] for s in res_all.values())
    m3 = [k.ask(r["вопрос"])[1]["ответ"] for r in bench]
    ch3 = sum(json.dumps(x, sort_keys=True) != json.dumps(y, sort_keys=True) for x, y in zip(m0, m3))
    out["вынуто_всё_про_задачи"] = {"задачи_в_чужую_область": "%d/%d" % (leak, len(tasks)), "прочие_как_до_вставки": "%d/%d" % (len(bench) - ch3, len(bench))}
    print("вынуто всё про задачи: задачи ушли в чужие области %d из %d; прочие как до вставки %d из %d" % (leak, len(tasks), len(bench) - ch3, len(bench)), flush=True)

    # без калькулятора: ядро само ловит неверную арифметику (проверка типа общие:Ответ). У решателя v2 (числа символами)
    # считает всегда код — этот режим к нему не относится.
    if json.load(open(os.path.join(solver, "паспорт.json"), encoding="utf-8"))["архитектура"] == "решатель2":
        out["файлы_весов_не_менялись"] = all(sha256_file(os.path.join(p, "веса.npz")) == h for p, h in hashes.items())
        name = "шаг4_%s%s.json" % (os.path.basename(solver), "_с_командами" if a.с_командами else "")
        json.dump(out, open(os.path.join(V4, "результаты", name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("файлы весов не менялись:", out["файлы_весов_не_менялись"], "| записано результаты/" + name)
        return
    tmp = os.path.join(V4, "блоки_задачи", "_без_калькулятора")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(solver, tmp)
    ps = json.load(open(os.path.join(tmp, "паспорт.json"), encoding="utf-8"))
    ps["настройки"]["калькулятор"] = False
    ps["имя"] = "задачи"
    json.dump(ps, open(os.path.join(tmp, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False)
    k4 = kernel(mil(a.с_командами) + [CLAIM, tmp])
    res_nc, _, _ = run_tasks(k4)
    out["без_калькулятора"] = res_nc
    print("без калькулятора:", {n: (s["доля"], "отказ проверки %d" % s["отказ_проверки_типа"]) for n, s in res_nc.items()}, flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    out["файлы_весов_не_менялись"] = all(sha256_file(os.path.join(p, "веса.npz")) == h for p, h in hashes.items())
    name = "шаг4_%s%s.json" % (os.path.basename(solver), "_с_командами" if a.с_командами else "")
    json.dump(out, open(os.path.join(V4, "результаты", name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("файлы весов не менялись:", out["файлы_весов_не_менялись"], "| записано результаты/" + name)


if __name__ == "__main__":
    main()
