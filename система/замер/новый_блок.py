# -*- coding: utf-8 -*-
"""Вставка нового блока в работающую систему: «команды» (обучен сторонним образом при замороженных «здоровье» и «право»).
Проверяет: язык 1.1 (добавлено понятие «область:команды») принимает старые блоки без переобучения; вставка с замером
меняет мало ответов старых блоков; новый блок отвечает на свои вопросы (MASSIVE test); снятие возвращает всё как было.
Запуск: python замер/новый_блок.py [имя_папки_нового_блока ...]. Пишет результаты/новый_блок.json."""
import collections
import json
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as О  # noqa: E402
from обучение import данные as D  # noqa: E402
from ядро import НЕ_ЗНАЮ  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main(папки):
    t0 = time.time()
    Н = О.наборы()
    qs = [r["вопрос"] for r in Н["общий_тест"]] + [r["текст"] for r in Н["флагманский_600"]]
    massive = D.команды("test")
    res = {}
    for папка_блока in папки:
        k, отч = О.система("основная")                      # старые блоки, язык 1.1, с проверкой языка
        старый_язык = {b.имя: b.паспорт["язык"]["версия"] for b in k.блоки.values()}
        до_massive = collections.Counter()
        for t, _ in massive:
            a, _ = k.спросить(t, подробно=False)
            до_massive[О.область(a)] += 1
        before = k.ответы_на(qs)
        p = os.path.join(О.БЛОКИ, "основная.з1", папка_блока)
        ok, msg, stats = k.подключить_с_замером(p, qs)
        assert ok, msg
        after = k.ответы_на(qs)
        стал_командой = sum(1 for x in after if x.startswith("ответ:команды") or x == "уточнить:команды")
        c = collections.Counter()
        for t, y in massive:
            a, rec = k.спросить(t)
            top = rec["кандидаты"][0]["ответ"] if rec["кандидаты"] else ""
            c["n"] += 1
            c["первый"] += top == "ответ:команды:%s" % y
            c["ответ_верен"] += a != НЕ_ЗНАЮ and a["вид"] == "ответ" and a["id"] == y and a["область"] == "команды"
            c["область_команды"] += a != НЕ_ЗНАЮ and a["область"] == "команды"
        k.снять(msg)
        back = k.ответы_на(qs)
        r = {"блоки_старого_языка": старый_язык, "язык_ядра": k.язык.версия, "вставка": stats,
             "вопросы_призывников_ставшие_командами": "%d/%d" % (стал_командой, len(qs)),
             "MASSIVE_test": {"вопросов": c["n"], "первый_ответ_верен": round(c["первый"] / c["n"], 4),
                              "ответ_верен_при_пороге": round(c["ответ_верен"] / c["n"], 4),
                              "область_команды": round(c["область_команды"] / c["n"], 4)},
             "MASSIVE_до_вставки_области": dict(до_massive),
             "после_снятия_как_до_вставки": "%d/%d" % (sum(x == y for x, y in zip(before, back)), len(qs)),
             "паспорт": {kk: json.load(open(os.path.join(p, "паспорт.json"), encoding="utf-8"))[kk] for kk in ("читает", "пишет")}}
        res[папка_блока] = r
        print(папка_блока, json.dumps(r, ensure_ascii=False), flush=True)
    json.dump(res, open(os.path.join(О.V8, "результаты", "новый_блок.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("готово за %.0f с" % (time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1:] or ["команды"])
