# -*- coding: utf-8 -*-
"""Учёба и работа совпадают: ядро (чистый Python + код архитектуры) и обучение (numpy пакетами) на одних и тех же весах дают
одни и те же числа — шину, вероятности ответов и «ничего». Проверяется на 400 вопросах, со всеми блоками и со снятым блоком.
Запуск: python тесты/тест_учёба_равна_работе.py [вариант]"""
import json
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
V8 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V8)
sys.path.insert(0, os.path.join(V8, "замер"))
import общее as О  # noqa: E402
from обучение import сеть as С  # noqa: E402


def блоки_обучения(k):
    out = []
    for b in k.блоки.values():
        ps = b.паспорт
        P = dict(np.load(os.path.join(b.папка, ps["веса"]["файл"]), allow_pickle=False))
        cfg = ps["настройки"]
        out.append(С.БлокУч(ps["имя"], ps["ответы"], ps["пишет"], ps["читает"], корзины=cfg["корзины"], размер=cfg["размер"],
                            граница=cfg["граница"], соль=cfg["соль"], init=P, заморожен=True, свёртка=cfg.get("свёртка", "среднее"),
                            масштаб_чтения=cfg.get("масштаб_чтения", 1.0)))
    return out


def сверить(k, тексты, снять=None):
    if снять:
        k.снять(снять)
    бл = блоки_обучения(k)
    сеть = С.Сеть(бл, проходов=k.схема.проходов, смешивание=k.схема.смешивание, веса_смешивания=k.схема.веса_смешивания)
    rows = [{"токены": k.язык.перевести(t)["токены"], "ответы": [], "понятия": {}} for t in тексты]
    keep = [i for i, r in enumerate(rows) if r["токены"]]
    rows = [rows[i] for i in keep]
    набор = С.Набор(rows, бл, list(k.язык.понятия))
    p, C = сеть.вперёд(набор, np.arange(len(rows)), np.ones((len(rows), len(бл)), np.float32))
    худшее = {"p": 0.0, "ничего": 0.0, "шина": 0.0}
    for j, i in enumerate(keep):
        a, rec = k.спросить(тексты[i])
        худшее["ничего"] = max(худшее["ничего"], abs(rec["p_ничего"] - float(p[j, 0])))
        for c in rec["кандидаты"]:
            худшее["p"] = max(худшее["p"], abs(c["p"] - float(p[j, сеть.ai[c["ответ"]]])))
        for kk, v in rec["шина"].items():
            худшее["шина"] = max(худшее["шина"], abs(v - float(C["m"][j, сеть.Ki[kk]])))
    return худшее, len(keep)


def main(вариант="основная"):
    Н = О.наборы()
    тексты = [r["вопрос"] for r in Н["общий_тест"][:150]] + [r["текст"] for r in Н["флагманский_600"][:250]]
    k, _ = О.система(вариант, проверять_язык=False)
    ok = True
    h, n = сверить(k, тексты)
    print("все блоки: %d вопросов, наибольшее расхождение: %s" % (n, json.dumps({x: float("%.2e" % y) for x, y in h.items()}, ensure_ascii=False)))
    ok &= h["p"] < 1e-3 and h["ничего"] < 1e-3 and h["шина"] < 2e-3
    имена = list(k.блоки)
    if len(имена) > 1:
        k, _ = О.система(вариант, проверять_язык=False)
        h, n = сверить(k, тексты, снять=имена[-1])
        print("снят блок %s: наибольшее расхождение: %s" % (имена[-1], json.dumps({x: float("%.2e" % y) for x, y in h.items()}, ensure_ascii=False)))
        ok &= h["p"] < 1e-3 and h["ничего"] < 1e-3 and h["шина"] < 2e-3
    print("учёба = работа:", "ДА" if ok else "НЕТ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*(sys.argv[1:2])))
