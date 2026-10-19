# -*- coding: utf-8 -*-
"""v9.1 проба 1: задумка выполнена или нет. Качество НЕ меряем.
Критерии: (1) работают все воткнутые на каждом запросе; (2) у ответа нет хозяина —
вклад чужого материален, снятие любого меняет ответ; (3) воткнул/вынул без переучки.
Варианты: круги 1–4 × затвор × преломление. Данные: 61 стыковой (эталон в обеих
областях) + проверка 200 для sanity."""
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


Я = мод(os.path.join(V91, "ядро.py"), "v91_ядро")
Б = мод(os.path.join(V91, "блоки.py"), "v91_блоки")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ВН = r"C:\ЯДРО-ОПЫТ\внешние"


def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def эталоны():
    import sys as _s
    _s.path.insert(0, r"C:\ЯДРО-ОПЫТ\система")
    from обучение import данные as D  # noqa: E402
    txt = {r["i"]: r["текст"] for r in json.load(open(os.path.join(ВН, "пул3_вопросы.json"), encoding="utf-8"))}
    зд = set(D.ответы_здоровья())
    пр = set(D.ответы_права())
    out = []
    for r in jl(os.path.join(ВН, "cowork_пул3.jsonl")):
        s = {"ответ:здоровье:%s" % a for a in r["ответы"]} | {"ответ:право:%s" % a for a in r["ответы"]}
        if (s & зд) and (s & пр):
            out.append((txt[r["i"]], sorted(s & зд), sorted(s & пр)))
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
        if prep is None:
            res.append(({}, {}))
        else:
            res.append(модель.спросить(prep))
    return res


def main():
    ст = эталоны()
    тексты = [t for t, _, _ in ст]
    проверка = [r["текст"] for r in json.load(open(os.path.join(ВН, "проверка_вопросы.json"), encoding="utf-8"))]
    base = {n: Б.загрузить(n) for n in ("здоровье", "право")}
    сетка = [dict(круги=R, tau=tau, преломление=tr) for R in (1, 2, 3, 4) for tau, tr in ([(2.0, True)] if R != 2 else [(2.0, True), (None, True), (2.0, False), (1.0, True)])]
    итог = {"стыковых": len(ст), "варианты": []}
    for cfg in сетка:
        м = Я.Модель(**cfg)
        м.воткнуть(base["здоровье"])
        м.воткнуть(base["право"])
        полные = прогнать(м, тексты)
        топы = [a.get("ответ", "") for a, _ in полные]
        # (1) работали все всегда
        покрытие = sum(1 for _, s in полные if sorted(s.get("работали", [])) == ["здоровье", "право"])
        # (2) совместность: чужой вклад ≥20% прямого; снятие меняет топ
        совм = чуж = 0
        with_tops = 0
        for (a, s) in полные:
            if not a.get("ответ"):
                continue
            with_tops += 1
            пр = abs(s.get("прямой", 0)) or 1e-9
            чужой = sum(abs(v) for w, v in s.get("шина_по_писателям", {}).items())
            чуж += чужой
            if чужой >= 0.2 * пр:
                совм += 1
        мз = Я.Модель(**cfg)
        мз.воткнуть(base["здоровье"])
        мп = Я.Модель(**cfg)
        мп.воткнуть(base["право"])
        топ_з = [a.get("ответ", "") for a, _ in прогнать(мз, тексты)]
        топ_п = [a.get("ответ", "") for a, _ in прогнать(мп, тексты)]
        смена_з = sum(1 for x, y in zip(топы, топ_з) if x != y)
        смена_п = sum(1 for x, y in zip(топы, топ_п) if x != y)
        # sanity на проверке: область не развалилась (качество не цель, просто фон)
        разм = {r["i"]: r for r in jl(os.path.join(ВН, "разметка_проверка.jsonl"))}
        ок = nq = 0
        for r in json.load(open(os.path.join(ВН, "проверка_вопросы.json"), encoding="utf-8")):
            w = разм[r["i"]]
            if w["область"] not in ("здоровье", "право"):
                continue
            prep = подготовить(м, r["текст"])
            if prep is None:
                continue
            a, _ = м.спросить(prep)
            nq += 1
            ок += a.get("область", "") == w["область"]
        итог["варианты"].append(dict(cfg, покрытие="%d/%d" % (покрытие, len(тексты)),
                                     совместные="%d/%d" % (совм, with_tops),
                                     средний_чужой=round(чуж / max(1, with_tops), 3),
                                     смена_без_здоровья="%d/%d" % (смена_з, len(тексты)),
                                     смена_без_права="%d/%d" % (смена_п, len(тексты)),
                                     sanity_проверка="%d/%d" % (ок, nq)))
        print(json.dumps(итог["варианты"][-1], ensure_ascii=False), flush=True)
    json.dump(итог, open(os.path.join(V91, "результаты", "проба1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
