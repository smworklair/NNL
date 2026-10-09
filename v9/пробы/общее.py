# -*- coding: utf-8 -*-
"""Общее для проб v9: данные (только чтение: рабочий проект, v8, v6, bench, флагманы, внешние), перевод на язык NNL-1 (правила v8),
наборы, оценка. Ничего не пишет вне v9/результаты."""
import sys

sys.dont_write_bytecode = True
import collections  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402

import numpy as np  # noqa: E402

V9 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
БАЗА = os.path.dirname(V9)
V8 = os.path.join(БАЗА, "v8")
V6 = os.path.join(БАЗА, "v6")
ПРОЕКТ = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"
РЕЗ = os.path.join(V9, "результаты")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def модуль(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


D8 = модуль(os.path.join(V8, "обучение", "данные.py"), "v8_данные")          # загрузчики данных v8 (только чтение)
ПРАВИЛА = модуль(os.path.join(V8, "язык", "правила.py"), "v8_правила")        # язык NNL-1: перевод вопроса в токены


def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def записать(имя, obj):
    os.makedirs(РЕЗ, exist_ok=True)
    with open(os.path.join(РЕЗ, имя), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


# ======================================================================== язык
_ток = {}


def токены(текст):
    t = _ток.get(текст)
    if t is None:
        t = ПРАВИЛА.разобрать(текст)["токены"]
        if len(_ток) < 300000:
            _ток[текст] = t
    return t


def разбор(текст):
    return ПРАВИЛА.разобрать(текст)


# ======================================================================== знание и наборы
def _join(*parts):
    out = []
    for p in parts:
        if isinstance(p, list):
            out.extend(str(x) for x in p)
        elif p:
            out.append(str(p))
    return " ".join(out)


ОТВ_З = lambda a: "ответ:здоровье:%s" % a  # noqa: E731
ОТВ_П = lambda t: "ответ:право:%s" % t  # noqa: E731
ВНЕ = "вне"


def область_ответа(a):
    return ВНЕ if a in (None, ВНЕ) else a.split(":")[1]


def ид_ответа(a):
    return "" if a in (None, ВНЕ) else a.split(":", 2)[2]


class Знание:
    """Всё, что системе разрешено знать (то же, что знала v8, но без искусственных копий: без обёрток, опечаток, «болтовни»).
    доки     — тексты документов: статьи и пункты Расписания, темы права (ответ — статья/тема);
    примеры  — размеченные вопросы: lay train, учитель train_t, lex train, живые пулы 1+2 (85 %; почти-повторы проверочных выброшены);
    фон      — тексты не про призыв (стандарт фона v2, 12000) — образцы «вне»;
    dev      — для подбора: lay dev, учитель dev_t, lex dev, живые 15 %, фон dev 1500."""

    def __init__(self, seed=1):
        self.статьи = D8.статьи()
        self.пункты = jl(os.path.join(ПРОЕКТ, "train/data/docs_points.jsonl"))
        self.темы = D8.темы()
        self.ответы = [ОТВ_З(a["article_no"]) for a in self.статьи] + [ОТВ_П(t["topic_id"]) for t in self.темы]
        self.ai = {a: j for j, a in enumerate(self.ответы)}
        self.глава = {ОТВ_З(a["article_no"]): int(a["chapter_no"]) for a in self.статьи}
        lay = jl(os.path.join(ПРОЕКТ, "train/data/queries_lay.jsonl"))
        teach = jl(os.path.join(ПРОЕКТ, "train/data/queries_claude_teacher.jsonl"))
        lex = jl(os.path.join(ПРОЕКТ, "rack/data/lex_questions.jsonl"))
        self.доки = []
        for a in self.статьи:
            self.доки.append((_join(a["title"], a["criteria"], a.get("notes")), ОТВ_З(a["article_no"]), "статья"))
        for p in self.пункты:
            self.доки.append((_join(p["title"], p["criteria"], p.get("notes")), ОТВ_З(p["article_no"]), "пункт"))
        for t in self.темы:
            self.доки.append((_join(t["title"], t["answer_hint"]), ОТВ_П(t["topic_id"]), "тема"))
        self.примеры = []      # (текст, [ответы], область или None, источник)
        for q in lay:
            if q["split"] == "train":
                self.примеры.append((q["text"], [ОТВ_З(q["article_no"])], "здоровье", "lay"))
        for q in teach:
            if q["split"] == "train_t":
                self.примеры.append((q["text"], [ОТВ_З(q["article_no"])], "здоровье", "учитель"))
        for q in lex:
            if q["split"] == "train":
                self.примеры.append((q["text"], [ОТВ_П(q["topic_id"])], "право", "lex"))
        live, self.выброшено = D8.живые_пулы(D8.Фильтр(D8.проверочные_тексты()))
        rnd = random.Random(seed)
        rnd.shuffle(live)
        cut = int(len(live) * 0.15)
        def _live(r):
            п = r["понятия"]
            обл = "здоровье" if п["область:здоровье"] == 1 else ("право" if п["область:право"] == 1 else ВНЕ)
            return (r["текст"], list(r["ответы"]), обл, r["источник"])
        self.живые_dev = [_live(r) for r in live[:cut]]
        for r in live[cut:]:
            self.примеры.append(_live(r))
        self.фон = D8.фон("train", 12000, seed)
        self.dev = []          # (текст, [ответы], область, группа)
        for q in lay:
            if q["split"] == "dev":
                self.dev.append((q["text"], [ОТВ_З(q["article_no"])], "здоровье", "lay dev"))
        for q in teach:
            if q["split"] == "dev_t":
                self.dev.append((q["text"], [ОТВ_З(q["article_no"])], "здоровье", "учитель dev"))
        for q in lex:
            if q["split"] == "dev":
                self.dev.append((q["text"], [ОТВ_П(q["topic_id"])], "право", "lex dev"))
        self.dev += [(t, a, o, "живые dev") for t, a, o, _ in self.живые_dev]
        self.фон_dev = D8.фон("dev", 1500, seed)
        self.lay = lay

    def сведения(self):
        c = collections.Counter(x[3] for x in self.примеры)
        return {"доков": len(self.доки), "примеров": len(self.примеры), "по_источникам": dict(c), "фон": len(self.фон),
                "dev": len(self.dev), "фон_dev": len(self.фон_dev), "ответов": len(self.ответы), "почти_повторов_выброшено": self.выброшено}


def bench():
    return jl(os.path.join(БАЗА, "bench", "bench.jsonl"))


def struct(split):
    return [r for r in jl(os.path.join(ПРОЕКТ, "train/data/queries_struct.jsonl")) if r["split"] == split]


def флагманский():
    return jl(os.path.join(БАЗА, "флагманы", "набор", "набор.jsonl"))


def оценка_флагманов():
    fl = os.path.join(БАЗА, "флагманы")
    if fl not in sys.path:
        sys.path.insert(0, fl)
    return модуль(os.path.join(fl, "оценка.py"), "оценка_флагманов_v9")


def флагманский_счёт(rows, ответы):
    """ответы: {ключ: (область, id)} → счёт как в флагманы/оценка.py (основная разметка)."""
    M = оценка_флагманов()
    items = M.срезы(rows)["всё · основная разметка"]
    ans = {k: {"ключ": k, "область": o, "id": i} for k, (o, i) in ответы.items()}
    c = M.счёт(items, ans)
    c["верных"] = c["зд_ok"] + c["пр_ok"]
    return c


def топ1_bench(rows, предсказано):
    """предсказано: список ответов (строка «ответ:обл:id» или None) по порядку rows → точность первого ответа по областям."""
    c = collections.Counter()
    for r, a in zip(rows, предсказано):
        d = r["область"]
        c[d, "n"] += 1
        c[d, "ok"] += a == ("ответ:%s:%s" % (d, r["ответ"]))
    return {d: round(c[d, "ok"] / c[d, "n"], 4) for d in ("здоровье", "право")}
