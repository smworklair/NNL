# -*- coding: utf-8 -*-
"""Единый запуск v4 (блоки уже обучены): тесты ядра → шаг 1 (блоки v3 на ядре v4) → шаг 2 (вставка области) →
шаг 2г (заявка + знание: выключение знания) → шаг 3 (решатель отдельно) → шаг 4 (задачи в ядре с военкоматом).
Запуск: python запуск.py [--решатель блоки_задачи/задачи_большой_с2] [--n 100] [--быстро]
  --быстро: шаг 3 и шаг 4 — по 30 задач из каждого набора (для проверки, что всё работает)."""
import argparse
import os
import subprocess
import sys
import time

V4 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run(title, args):
    print("\n" + "=" * 100 + "\n" + title + "\n" + "=" * 100, flush=True)
    t = time.time()
    p = subprocess.run([sys.executable] + args, cwd=V4, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    print("[%s: код %d, %.0f с]" % (title, p.returncode, time.time() - t), flush=True)
    return p.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--решатель", default="блоки_задачи/задачи_большой_с2")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--быстро", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(os.path.join(V4, a.решатель, "паспорт.json")):
        a.решатель = "блоки_задачи/задачи_малый_с2"
    n = 30 if a.быстро else a.n
    ok = {}
    ok["тесты ядра"] = run("Тесты ядра (блоки-пустышки)", ["тесты/тест_ядра.py"])
    ok["шаг 1"] = run("Шаг 1: блоки v3 на ядре v4", ["шаг1_v3_на_ядре_v4.py"])
    ok["шаг 2"] = run("Шаг 2: вставка третьей области (блоки с калиброванной заявкой)", ["шаг2_вставка_области.py", "блоки_ф2к", "шаг2в.json"])
    ok["шаг 2г"] = run("Шаг 2г: заявка + знание, выключение знания", ["шаг2г_заявка_и_знание.py"])
    ok["шаг 3"] = run("Шаг 3: решатель отдельно (%s)" % a.решатель, ["шаг3_оценка_решателя.py", a.решатель, "--n", str(n)])
    ok["шаг 4"] = run("Шаг 4: задачи в ядре вместе с военкоматом", ["шаг4_задачи_в_ядре.py", a.решатель, "--n", str(n)])
    print("\nИТОГ:", ", ".join("%s — %s" % (k, "ок" if v else "ОШИБКА") for k, v in ok.items()))
    sys.exit(0 if all(ok.values()) else 1)


if __name__ == "__main__":
    main()
