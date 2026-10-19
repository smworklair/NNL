# -*- coding: utf-8 -*-
"""v9.1 проба 2: прямой путь запрещён (только_через_поле=True).
Никто в одиночку ответить не может по построению. Метрики:
покрытие (все работают) · ответы целой · ответы соло (ждём ~0) ·
смена при снятии (ждём ~все) · взаимодействие (поле полного vs поле без блока).
Качество НЕ цель."""
import json
import os
import sys

sys.dont_write_bytecode = True
V91 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, V91)


def мод(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


Я = мод(os.path.join(V91, "ядро.py"), "v91_ядро2")
Б = мод(os.path.join(V91, "блоки.py"), "v91_блоки2")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ВН = r"C:\ЯДРО-ОПЫТ\внешние"


def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def эталоны():
    sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\система")
    from обучение import данные as D  # noqa: E402
    txt = {r["i"]: r["текст"] for r in json.load(open(os.path.join(ВН, "пул3_вопросы.json"), encoding="utf-8"))}
    зд = set(D.ответы_здоровья())
    пр = set(D.ответы_права())
    out = []
    for r in jl(os.path.join(ВН, "cowork_пул3.jsonl")):
        s = {"ответ:здоровье:%s" % a for a in r["ответы"]} | {"ответ:право:%s" % a for a in r["ответы"]}
        if (s & зд) and (s & пр):
            out.append(txt[r["i"]])
    return out


def подготовить(модель, текст):
    ток = Б.токены(текст)
    if not ток:
        return None
    return {n: (Б.кодировать(б, ток)[1], ток) for n, б in модель.воткнуты.items()}


def прогнать(модель, вопросы):
    res = []
    for t in вопросы:
        prep = подготовить(модель, t)
        res.append(модель.спросить(prep) if prep else ({}, {}))
    return res


def поле_дельта(полные, урезанные):
    """Средний модуль разницы полей: блоки влияют друг на друга через среду."""
    ds = []
    for (_, s1), (_, s2) in zip(полные, урезанные):
        f1, f2 = s1.get("поле"), s2.get("поле")
        if f1 and f2 and len(f1) == len(f2):
            ds.append(sum(abs(a - b) for a, b in zip(f1, f2)) / len(f1))
    return round(sum(ds) / max(1, len(ds)), 4)


def main():
    тексты = эталоны()
    base = {n: Б.загрузить(n) for n in ("здоровье", "право")}
    итог = {"стыковых": len(тексты), "режим": "только_через_поле", "варианты": []}
    for R in (1, 2, 3, 4):
        cfg = dict(круги=R, tau=2.0, преломление=True, только_через_поле=True)
        м = Я.Модель(**cfg)
        м.воткнуть(base["здоровье"])
        м.воткнуть(base["право"])
        полные = прогнать(м, тексты)
        топы = [a.get("ответ", "") for a, _ in полные]
        покрытие = sum(1 for _, s in полные if sorted(s.get("работали", [])) == ["здоровье", "право"])
        ответов = sum(1 for t in топы if t)
        мз = Я.Модель(**cfg)
        мз.воткнуть(base["здоровье"])
        мп = Я.Модель(**cfg)
        мп.воткнуть(base["право"])
        сз = прогнать(мз, тексты)
        сп = прогнать(мп, тексты)
        соло_з = sum(1 for a, _ in сз if a.get("ответ"))
        соло_п = sum(1 for a, _ in сп if a.get("ответ"))
        топ_з = [a.get("ответ", "") for a, _ in сз]
        топ_п = [a.get("ответ", "") for a, _ in сп]
        смена_з = sum(1 for x, y in zip(топы, топ_з) if x != y)
        смена_п = sum(1 for x, y in zip(топы, топ_п) if x != y)
        rec = dict(круги=R, покрытие="%d/%d" % (покрытие, len(тексты)),
                   ответов_целой="%d/%d" % (ответов, len(тексты)),
                   ответов_соло_зд=соло_з, ответов_соло_пр=соло_п,
                   смена_без_здоровья="%d/%d" % (смена_з, len(тексты)),
                   смена_без_права="%d/%d" % (смена_п, len(тексты)),
                   поле_дельта_без_здоровья=поле_дельта(полные, сз),
                   поле_дельта_без_права=поле_дельта(полные, сп))
        итог["варианты"].append(rec)
        print(json.dumps(rec, ensure_ascii=False), flush=True)
    json.dump(итог, open(os.path.join(V91, "результаты", "проба2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
