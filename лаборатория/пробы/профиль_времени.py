# -*- coding: utf-8 -*-
"""Профиль времени на один вопрос v8 (пункт 1 плана v9.2).
Гоняет систему `основная_внешние` на наборе вопросов, разбивает время по стадиям:
  - разбор текста (язык.перевести)
  - проход 1 (блоки пишут на шину)
  - смешивание на шине (ядро._смешать)
  - проход 2 (блоки читают шину и дают счёты)
  - сборка ответа (softmax, выбор топ-3, разложение)
  - прочее (сессия, журнал и т.д.)
Пишет v9/результаты/профиль_времени.json."""
import cProfile
import json
import os
import pstats
import sys
import time

sys.dont_write_bytecode = True
from лаба_общее import О  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, О.V8)
from ядро import Ядро, Язык  # noqa: E402

ВЫХОД = os.path.join(О.БАЗА, "лаборатория", "результаты", "профиль_времени.json")


def вопросы_стыки():
    lab = json.load(open(os.path.join(О.БАЗА, "лаборатория", "результаты", "лаба_стыки_полные.json"), encoding="utf-8"))
    return [r["текст"] for r in lab["вопросы"]]


def вопросы_bench(n=200):
    rows = О.наборы()["общий_тест"]
    return [r["вопрос"] for r in rows[:n]]


def профиль(к, texts):
    """Возвращает (суммарное_с, {стадия: мс}) по серии вопросов."""
    times = {"разбор": 0.0, "проход1": 0.0, "смешивание": 0.0, "проход2": 0.0, "сборка": 0.0}
    t0 = time.perf_counter()
    for t in texts:
        t1 = time.perf_counter()
        разбор = к.язык.перевести(t)
        t2 = time.perf_counter()
        токены = разбор["токены"]
        блоки = list(к.блоки.values())
        t3 = time.perf_counter()
        вклады = {}
        for b in блоки:
            c = b.arch.проход1(b.obj, токены)
            вклады[b.имя] = c
        t4 = time.perf_counter()
        шина, писатели = к._смешать(вклады)
        t5 = time.perf_counter()
        счёты = {}
        for b in блоки:
            v = {k: шина[k] for k in b.читает if k in шина} if к.схема.проходов == 2 else {}
            s = b.arch.проход2(b.obj, токены, v)
            счёты.update(s)
        t6 = time.perf_counter()
        # сборка ответа
        import math
        m = max([0.0] + list(счёты.values()))
        z = math.exp(-m) + sum(math.exp(x - m) for x in счёты.values())
        p = {a: math.exp(x - m) / z for a, x in счёты.items()}
        порядок = sorted(p, key=lambda a: (-p[a], a))
        t7 = time.perf_counter()
        times["разбор"] += t2 - t1
        times["проход1"] += t4 - t3
        times["смешивание"] += t5 - t4
        times["проход2"] += t6 - t5
        times["сборка"] += t7 - t6
    total = time.perf_counter() - t0
    остальное = max(0.0, total - sum(times.values()))
    times["прочее"] = остальное
    return total, times


def main():
    язык = О.Язык(О.ЯЗЫК_ПАПКА)
    k, _ = О.система("основная_внешние", 1, язык=язык)

    стыки = вопросы_стыки()
    bench = вопросы_bench(200)

    # прогрев
    if стыки:
        k.спросить(стыки[0])
    if bench:
        k.спросить(bench[0])

    рез = {}
    for имя, texts, n in (("стыки_61", стыки, len(стыки)), ("bench_200", bench, len(bench))):
        print("\n=== %s (%d вопросов) ===" % (имя, n))
        проф = cProfile.Profile()
        проф.enable()
        total, parts = профиль(k, texts)
        проф.disable()

        sio = ""
        ps = pstats.Stats(проф, stream=open(os.devnull, "w"))
        ps.strip_dirs().sort_stats("cumulative")
        top = []
        for func, (cc, nc, tt, ct, callers) in ps.stats.items():
            top.append((ct, tt, func))
        top.sort(reverse=True)
        top = top[:15]

        рез[имя] = {
            "вопросов": n,
            "всего_с": total,
            "на_вопрос_мс": round(1000 * total / n, 3),
            "по_стадиям_мс": {k: round(1000 * v / n, 3) for k, v in parts.items()},
            "cumulative_top15": [
                {"функция": str(func), "cumtime_ms": round(1000 * ct / n, 3), "tottime_ms": round(1000 * tt / n, 3)}
                for ct, tt, func in top
            ],
        }
        print(json.dumps({k: v for k, v in рез[имя].items() if k != "cumulative_top15"}, ensure_ascii=False, indent=1))
        print("Топ-10 по cumulative:")
        for ct, tt, func in top[:10]:
            print("  %.3f ms/вопрос  %s" % (1000 * ct / n, func))

    os.makedirs(os.path.dirname(ВЫХОД), exist_ok=True)
    json.dump(рез, open(ВЫХОД, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nзаписано:", ВЫХОД)


if __name__ == "__main__":
    main()
