# -*- coding: utf-8 -*-
"""Тесты ядра v8 на маленьких блоках (случайные веса, не обучены). Проверяют устройство, а не качество.
Запуск: python тесты/тест_ядра.py"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

sys.dont_write_bytecode = True
V8 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V8)
from ядро import НЕ_ЗНАЮ, Схема, Ядро, Язык, sha256_file  # noqa: E402
from обучение import сеть as С  # noqa: E402

ЯЗ = Язык(os.path.join(V8, "язык"))
ARCH = os.path.join(V8, "архитектуры")
ИТОГ = []


def check(name, cond, detail=""):
    ИТОГ.append((name, bool(cond)))
    print(("ок   " if cond else "СБОЙ ") + name + (" — " + str(detail) if detail and not cond else ""), flush=True)


def сделать_блок(папка, имя, ответы, пишет, читает, seed, контроль=None, сдвиг=None):
    b = С.БлокУч(имя, ответы, пишет, читает, корзины=64, размер=4, seed=seed)
    rng = np.random.RandomState(seed)
    for k in b.P:
        b.P[k] = (rng.randn(*b.P[k].shape)).astype(np.float32)
    if сдвиг is not None:
        b.P["A"][:] = 0
        b.P["a"][:] = сдвиг
    os.makedirs(папка, exist_ok=True)
    w = os.path.join(папка, "веса.npz")
    b.сохранить(w)
    rows = контроль or [{"вопрос": "у меня астма", "понятия": {k: 1 for k in пишет}}, {"вопрос": "привет", "понятия": {k: 0 for k in пишет}}]
    with open(os.path.join(папка, "контроль.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ps = {"имя": имя, "версия": 1, "роль": "тестовый блок", "область": "тест", "архитектура": "мешок_шина",
          "настройки": {"корзины": 64, "размер": 4, "граница": 8.0, "соль": имя, "свёртка": "корень"},
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": b.чисел()},
          "язык": ЯЗ.паспорт_языка(пишет, читает), "пишет": пишет, "читает": читает, "ответы": ответы,
          "контроль": {"файл": "контроль.jsonl"}, "обучение": {"тест": True}, "родитель": None}
    json.dump(ps, open(os.path.join(папка, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return папка


def правка_паспорта(src, dst, fn):
    shutil.copytree(src, dst)
    p = os.path.join(dst, "паспорт.json")
    ps = json.load(open(p, encoding="utf-8"))
    fn(ps)
    json.dump(ps, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return dst


def main():
    tmp = tempfile.mkdtemp(prefix="v8_тест_")
    try:
        # ---- 1. пустое ядро, numpy не нужен
        k = Ядро(ЯЗ, ARCH)
        a, rec = k.спросить("у меня астма, возьмут в армию?")
        check("пустое ядро отвечает «не знаю»", a == НЕ_ЗНАЮ and rec["причина"] == "нет подключённых блоков", rec["причина"])
        code = "import sys; sys.path.insert(0, %r); import ядро; k = ядро.Ядро(%r, %r); k.спросить('тест'); print('numpy' in sys.modules)" % (
            V8, os.path.join(V8, "язык"), ARCH)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8").stdout.strip()
        check("ядро и язык работают без numpy", out == "False", out)
        src = open(os.path.join(V8, "ядро", "ядро.py"), encoding="utf-8").read()
        check("в коде ядра нет numpy и нет файлов весов", "import numpy" not in src and
              not any(f.endswith((".npz", ".npy", ".pt")) for f in os.listdir(os.path.join(V8, "ядро"))))
        check("в языке нет файлов весов", not any(f.endswith((".npz", ".npy", ".pt")) for _, _, fs in os.walk(os.path.join(V8, "язык")) for f in fs))

        # ---- 2. два блока: подключение, ответ, разложение
        z_ans = ["ответ:здоровье:1", "ответ:здоровье:2"]
        p_ans = ["ответ:право:x", "ответ:право:y", "ответ:право:z"]
        bz = сделать_блок(os.path.join(tmp, "з"), "з", z_ans, ["область:здоровье", "глава:1"], ["область:право", "акт:кас"], 1)
        bp = сделать_блок(os.path.join(tmp, "п"), "п", p_ans, ["область:право", "акт:кас"], ["область:здоровье", "глава:1"], 2)
        k = Ядро(ЯЗ, ARCH)
        ok1 = k.подключить(bz, проверять_язык=False)
        ok2 = k.подключить(bp, проверять_язык=False)
        check("подключение двух блоков", ok1[0] and ok2[0], (ok1[1], ok2[1]))
        qs = ["у меня астма, возьмут?", "повестка пришла, что делать", "какая погода завтра", "плоскостопие и отсрочка по учёбе",
              "у брата нет астмы", "", "сколько служить по призыву?"]
        conv = True
        for q in qs:
            a, rec = k.спросить(q)
            for c in rec["кандидаты"]:
                conv &= c["сходится"]
            conv &= set(rec["шина"]) == {"область:здоровье", "глава:1", "область:право", "акт:кас"}
        check("разложение счёта на вклады блоков сходится точно; на шине все понятия", conv)
        a, rec = k.спросить("повестка пришла, что делать")
        c = rec["кандидаты"][0]
        check("в журнале: путь, версии, хеши, вклады", all(x in rec for x in ("блоки", "шина", "вклады", "кандидаты"))
              and set(c["через_шину"]) <= {"з", "п"} and len(rec["блоки"]) == 2 and len(rec["блоки"][0]["sha256"]) == 12)

        # ---- 3. смешивание: два писателя одного понятия → среднее (и веса схемы)
        bz2 = сделать_блок(os.path.join(tmp, "з2"), "з2", ["ответ:здоровье:3"], ["область:здоровье"], [], 3)
        k.подключить(bz2, проверять_язык=False)
        a, rec = k.спросить("у меня астма")
        v = rec["вклады"]
        mean = (v["з"]["область:здоровье"] + v["з2"]["область:здоровье"]) / 2
        check("смешивание «среднее»: на шине среднее двух писателей", abs(rec["шина"]["область:здоровье"] - mean) < 1e-3,
              (rec["шина"]["область:здоровье"], mean))
        k.схема = Схема({"веса_смешивания": {"з2": 3.0}})
        a, rec = k.спросить("у меня астма")
        v = rec["вклады"]
        w = (v["з"]["область:здоровье"] + 3 * v["з2"]["область:здоровье"]) / 4
        check("веса смешивания из схемы", abs(rec["шина"]["область:здоровье"] - w) < 1e-3)
        conv = all(c["сходится"] for c in rec["кандидаты"])
        check("разложение сходится и при двух писателях с весами", conv)
        k.схема = Схема()
        k.снять("з2")

        # ---- 4. снятие и возврат
        before = k.ответы_на(qs)
        k.снять("п")
        a, rec = k.спросить("повестка пришла, что делать")
        check("после снятия ответов блока нет нигде", not any(x["ответ"].startswith("ответ:право") for x in rec["кандидаты"])
              and "область:право" not in rec["шина"])
        k.подключить(bp, проверять_язык=False)
        check("вернули блок — ответы те же, что до снятия", k.ответы_на(qs) == before)

        # ---- 5. один проход: блоки не видят шину
        a2, rec2 = k.спросить("повестка пришла")
        k.схема = Схема({"проходов": 1})
        a1, rec1 = k.спросить("повестка пришла")
        k.схема = Схема()
        s2 = {c["ответ"]: c["счёт"] for c in rec2["кандидаты"]}
        s1 = {c["ответ"]: c["счёт"] for c in rec1["кандидаты"]}
        common = set(s1) & set(s2)
        check("схема «1 проход» меняет счёты (шина не читается), «2 прохода» — читает",
              any(abs(s1[x] - s2[x]) > 1e-6 for x in common) and all(not c["через_шину"] for c in rec1["кандидаты"]))

        # ---- 6. отказы при подключении
        k2 = Ядро(ЯЗ, ARCH)
        bad = os.path.join(tmp, "плохой_хеш")
        shutil.copytree(bz, bad)
        with open(os.path.join(bad, "веса.npz"), "r+b") as f:
            f.seek(200)
            x = f.read(1)
            f.seek(200)
            f.write(bytes([x[0] ^ 1]))
        r = k2.подключить(bad, проверять_язык=False)
        check("отказ: веса не совпадают с паспортом", not r[0] and "sha256" in " ".join(r[1]), r[1])
        r = k2.подключить(правка_паспорта(bz, os.path.join(tmp, "пр"), lambda ps: ps["язык"].update(правила="0" * 64)), проверять_язык=False)
        check("отказ: блок учился под другие правила языка", not r[0] and "правила языка" in " ".join(r[1]), r[1])
        r = k2.подключить(правка_паспорта(bz, os.path.join(tmp, "пон"), lambda ps: ps["язык"]["понятия"].update({"область:здоровье": "1" * 64})),
                          проверять_язык=False)
        check("отказ: смысл понятия изменился", not r[0] and "смысл понятия" in " ".join(r[1]), r[1])
        r = k2.подключить(правка_паспорта(bz, os.path.join(tmp, "нет"), lambda ps: ps["пишет"].append("область:космос")), проверять_язык=False)
        check("отказ: понятия нет в языке", not r[0] and "нет в языке" in " ".join(r[1]), r[1])
        r = k2.подключить(правка_паспорта(bz, os.path.join(tmp, "отв"), lambda ps: ps["ответы"].append("ответ:космос:1")), проверять_язык=False)
        check("отказ: ответ не по языку (область не зарегистрирована)", not r[0] and "форме языка" in " ".join(r[1]), r[1])
        r = k2.подключить(правка_паспорта(bz, os.path.join(tmp, "чис"), lambda ps: ps["веса"].update(чисел=1)), проверять_язык=False)
        check("отказ: число чисел в весах не равно паспорту", not r[0] and "чисел" in " ".join(r[1]), r[1])
        k2.подключить(bz, проверять_язык=False)
        dup = сделать_блок(os.path.join(tmp, "дубль"), "дубль", ["ответ:здоровье:1"], [], [], 5)
        r = k2.подключить(dup, проверять_язык=False)
        check("отказ: у ответа уже есть хозяин", not r[0] and "хозяин" in " ".join(r[1]), r[1])
        k3 = Ядро(ЯЗ, ARCH, схема=Схема({"бюджет_чисел": 100}))
        r = k3.подключить(bz, проверять_язык=False)
        check("отказ: превышен бюджет чисел схемы", not r[0] and "бюджет" in " ".join(r[1]), r[1])
        k4 = Ядро(ЯЗ, ARCH, схема=Схема({"блоки": ["п"]}))
        r = k4.подключить(bz, проверять_язык=False)
        check("отказ: блока нет в схеме", not r[0] and "нет в схеме" in " ".join(r[1]), r[1])
        # проверка языка блока: число на шине не значит «логарифм шансов»
        ctrl = [{"вопрос": "вопрос номер %d про здоровье" % i, "понятия": {"область:здоровье": i % 2}} for i in range(40)]
        liar = сделать_блок(os.path.join(tmp, "лжец"), "лжец", ["ответ:здоровье:7"], ["область:здоровье"], [], 6, контроль=ctrl, сдвиг=6.0)
        r = Ядро(ЯЗ, ARCH).подключить(liar)
        check("отказ: блок пишет на шину числа не того смысла (проверка языка на контроле)", not r[0] and "ECE" in " ".join(r[1]), r[1])

        # ---- 7. сбой блока: ядро работает дальше
        k5 = Ядро(ЯЗ, ARCH)
        k5.подключить(bz, проверять_язык=False)
        k5.подключить(bp, проверять_язык=False)
        orig = k5.блоки["п"].arch

        class Падающий:
            def __getattr__(self, n):
                return getattr(orig, n)

            def проход2(self, obj, токены, шина):
                raise RuntimeError("кастрюля упала")
        k5.блоки["п"].arch = Падающий()
        a, rec = k5.спросить("повестка пришла, что делать")
        check("сбой блока: ядро отмечает «куска нет» и собирает ответ из остального",
              "п" in rec["сбои"] and "кастрюля" in rec["сбои"]["п"] and all(not c["ответ"].startswith("ответ:право") for c in rec["кандидаты"]))
        k5.блоки["п"].arch = orig

        # ---- 8. сессии
        k6 = Ядро(ЯЗ, ARCH)
        k6.подключить(bz, проверять_язык=False)
        k6.подключить(bp, проверять_язык=False)
        fresh = k6.ответы_на(qs)
        s1 = k6.сессия()
        for q in qs * 3:
            s1.спросить(q)
        n1 = len(s1.журнал)
        картина_ок = s1.картина["вопросов"] == len(qs) * 3 and "здоровье" in s1.картина["области"]
        s1.закрыть()
        s2 = k6.сессия()
        ans2 = []
        for q in qs:
            a, _ = s2.спросить(q)
            ans2.append(a if a == НЕ_ЗНАЮ else (a["вид"], a.get("id")))
        fresh2 = [a if a == НЕ_ЗНАЮ else (a["вид"], a.get("id")) for a in (k6.спросить(q)[0] for q in qs)]
        check("сессия: журнал и картина свои; закрытие стирает; следующая сессия отвечает как новое ядро",
              n1 == len(qs) * 3 and картина_ок and s1.журнал == [] and s1.картина["вопросов"] == 0
              and len(s2.журнал) == len(qs) and s2.картина["вопросов"] == len(qs) and ans2 == fresh2)
        try:
            s1.спросить("ещё")
            closed = False
        except RuntimeError:
            closed = True
        check("закрытая сессия не принимает вопросы", closed)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in ИТОГ if not ok]
    print("\nИТОГО: %d из %d" % (len(ИТОГ) - len(bad), len(ИТОГ)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
