# -*- coding: utf-8 -*-
"""Данные лабораторной v8. Всё — только чтение: рабочий проект военкомата, v6/реальные, внешние, флагманы/набор.

Обучение (train) и dev:
  здоровье: тексты статей и пунктов Расписания, lay train, учитель train_t (+ живые формы: обёртки, опечатки — как в v6);
  право:    lex train, тексты 44 тем (+ обёртки, опечатки);
  живые:    пул 1 (calm_topic, разметка Claude) + пул 2 (архив Mail.ru, разметка Muse Spark), спорные выброшены,
            15 % — dev, остальное — обучение (оригинал ×2 + 4 живые копии);
  фон:      стандарт фона v2 (заголовки, отзывы, аннотации) — 12000 на обучение, 1500 на dev.
Проверочные наборы не читаются для обучения: почти-повторы любых проверочных вопросов (куски по 5 букв, Жаккар ≥ 0,5)
выбрасываются из живых пулов — как в v6 (обучение/реальные.py).
Метки понятий языка у каждого вопроса: область:здоровье, область:право (1/0/неизвестно), глава:N, акт:X."""
import ast
import importlib.util
import json
import os
import random
import re

V8 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
БАЗА = os.path.dirname(V8)
ПРОЕКТ = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ" if os.name == "nt" else \
    os.path.join(os.path.dirname(БАЗА), "ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ")
V6 = os.path.join(БАЗА, "архив", "ядро_v6")
ВНЕШНИЕ = os.path.join(БАЗА, "внешние")
АКТЫ = {"53fz": "акт:53фз", "pp565": "акт:пп565", "pp663": "акт:пп663", "pp719": "акт:пп719", "kas": "акт:кас",
        "koap": "акт:коап", "ukrf": "акт:укрф", "127fz": "акт:127фз", "59fz": "акт:59фз"}
ГЛАВ = 17

# ---- живые формы вопроса (перенесено из v6/обучение/обучить_заявку_здоровья.py без изменений) ----
FRAMES = ["у меня {x}. берут ли в армию?", "{x} — возьмут ли в армию?", "берут ли в армию, если {x}?", "если у меня {x}, заберут ли в армию?",
          "диагноз: {x}. годен ли к службе?", "{x}, какая будет категория годности?", "сыну поставили: {x}. возьмут его служить?",
          "{x}. дают ли освобождение от армии?", "годен ли я, если {x}?", "призовут ли меня, у меня {x}", "врач написал {x}, что будет с армией?",
          "{x}. это статья или нет?", "служить с таким можно? {x}", "{x} и армия — совместимы?", "здравствуйте, {x}. в армию заберут?"]
ALPHA = "абвгдежзийклмнопрстуфхцчшщъыьэюя"
PRE = ["помогите", "всем привет", "здравствуйте", "подскажите пожалуйста", "кто знает", "вопрос такой", "ребят", "срочно", "слушайте", "люди добрые"]
POST = ["что делать", "кто знает", "как быть", "помогите", "подскажите", "заранее спасибо", "не знаю что делать", "очень надо", "пожалуйста ответьте"]


def chatter(t, rnd):
    t = t.rstrip(".?!")
    r = rnd.random()
    if r < 0.4:
        t = rnd.choice(PRE) + " " + t
    elif r < 0.8:
        t = t + " " + rnd.choice(POST)
    else:
        t = rnd.choice(PRE) + " " + t + " " + rnd.choice(POST)
    if rnd.random() < 0.3:
        w = t.split()
        i = rnd.randrange(len(w))
        w[i] = w[i].upper()
        t = " ".join(w)
    return t


def typo(t, rnd):
    w = list(t.lower())
    for _ in range(rnd.randint(1, 3)):
        if len(w) < 4:
            break
        i, op = rnd.randrange(1, len(w) - 1), rnd.randrange(4)
        if op == 0:
            del w[i]
        elif op == 1:
            w[i], w[i + 1] = w[i + 1], w[i]
        elif op == 2:
            w[i] = rnd.choice(ALPHA)
        else:
            w.insert(i, rnd.choice(ALPHA))
    s = "".join(w)
    return s.replace(",", "") if rnd.random() < 0.5 else s


def live(t, rnd, n):
    return [typo(t, rnd) if k % 2 == 0 else chatter(t, rnd) for k in range(n)]


# ---- чтение ----
def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _join(*parts):
    out = []
    for p in parts:
        if isinstance(p, list):
            out.extend(str(x) for x in p)
        elif p:
            out.append(str(p))
    return " ".join(out)


def статьи():
    return jl(os.path.join(ПРОЕКТ, "train/data/docs_articles.jsonl"))


def темы():
    return json.load(open(os.path.join(ПРОЕКТ, "rack/data/lex_topics.json"), encoding="utf-8"))


def глава_статьи():
    return {a["article_no"]: int(a["chapter_no"]) for a in статьи()}


def акты_темы():
    out = {}
    for t in темы():
        prov = t["provision_ids"]
        prov = ast.literal_eval(prov) if isinstance(prov, str) else prov
        out[t["topic_id"]] = sorted({АКТЫ[p.split(":")[0]] for p in prov})
    return out


def ответы_здоровья():
    return ["ответ:здоровье:%s" % a["article_no"] for a in статьи()]


def ответы_права():
    return ["ответ:право:%s" % t["topic_id"] for t in темы()]


_ГЛ, _АК = None, None


def строка(текст, здоровье, право, статьи_=(), темы_=(), источник="", группа=None):
    """здоровье/право: 1, 0 или None (неизвестно). статьи_/темы_: эталонные ответы (может быть пусто)."""
    global _ГЛ, _АК
    if _ГЛ is None:
        _ГЛ, _АК = глава_статьи(), акты_темы()
    п = {"область:здоровье": здоровье, "область:право": право}
    if статьи_:
        gl = {_ГЛ[str(a)] for a in статьи_}
        for n in range(1, ГЛАВ + 1):
            п["глава:%d" % n] = int(n in gl)
    else:
        for n in range(1, ГЛАВ + 1):
            п["глава:%d" % n] = None if здоровье == 1 else 0
    if темы_:
        ak = set()
        for t in темы_:
            ak.update(_АК[t])
        for a in АКТЫ.values():
            п[a] = int(a in ak)
    else:
        for a in АКТЫ.values():
            п[a] = None if право == 1 else 0
    ответы = ["ответ:здоровье:%s" % a for a in статьи_] + ["ответ:право:%s" % t for t in темы_]
    return {"текст": текст, "понятия": п, "ответы": ответы, "источник": источник, "группа": группа}


# ---- проверочные тексты и почти-повторы ----
def _grams(t):
    s = " ".join(re.findall(r"[а-яa-z0-9]+", t.lower().replace("ё", "е")))
    return {s[i:i + 5] for i in range(max(1, len(s) - 4))}


def проверочные_тексты():
    out = [r["вопрос"] for r in jl(os.path.join(БАЗА, "бенчмарки", "bench", "bench.jsonl"))]
    for f in ("разметка.jsonl", "разметка_отложенные.jsonl", "разметка_свежие.jsonl"):
        out += [r["вопрос"] for r in jl(os.path.join(V6, "реальные", f))]
    out += [r["вопрос"] for r in jl(os.path.join(V6, "реальные", "архив", "разметка_свежие2.jsonl"))]
    out += [r["текст"] for r in jl(os.path.join(БАЗА, "бенчмарки", "флагманы", "набор", "набор.jsonl"))]
    out += [r["текст"] for r in jl(os.path.join(ВНЕШНИЕ, "фразы.jsonl"))]
    out += [r["текст"] for r in jl(os.path.join(V6, "реальные", "отрицания.jsonl"))]
    return out


class Фильтр:
    def __init__(self, texts, порог=0.5):
        self.tg = [_grams(t) for t in texts]
        self.index = {}
        for j, g in enumerate(self.tg):
            for x in g:
                self.index.setdefault(x, []).append(j)
        self.порог = порог

    def близко(self, t):
        g = _grams(t)
        hits = {}
        for x in g:
            for j in self.index.get(x, ()):
                hits[j] = hits.get(j, 0) + 1
        return max((c / len(g | self.tg[j]) for j, c in hits.items()), default=0.0) >= self.порог


def _метки_пула1():
    spec = importlib.util.spec_from_file_location("пул_метки_v6", os.path.join(V6, "реальные", "пул_метки.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def живые_пулы(фильтр):
    """[(строка, исх. текст)] пул 1 + пул 2 без спорных и без почти-повторов проверочных; и число выброшенных."""
    rows, dropped = [], 0
    texts = json.load(open(os.path.join(V6, "реальные", "пул_тексты.json"), encoding="utf-8"))
    M = _метки_пула1()
    for i, t in enumerate(texts):
        if i in M.SKIP:
            continue
        if фильтр.близко(t):
            dropped += 1
            continue
        P, H = M.P.get(i), M.H.get(i)
        rows.append(строка(t, int(H is not None), int(P is not None), H or (), P or (), "пул1"))
    t2 = json.load(open(os.path.join(V6, "реальные", "архив", "пул2_тексты.json"), encoding="utf-8"))
    for r in jl(os.path.join(ВНЕШНИЕ, "разметка_пул2.jsonl")):
        if r["область"] == "спорно":
            continue
        t = t2[r["i"]]["текст"]
        if фильтр.близко(t):
            dropped += 1
            continue
        a = r["ответы"]
        rows.append(строка(t, int(r["область"] == "здоровье"), int(r["область"] == "право"),
                           a if r["область"] == "здоровье" else (), a if r["область"] == "право" else (), "пул2"))
    return rows, dropped


def фон(split, n, seed=1):
    rows = [r["текст"] for r in jl(os.path.join(V6, "стандарт", "фон2_%s.jsonl" % split))]
    random.Random(seed).shuffle(rows)
    return rows[:n]


def собрать(seed=1):
    """Возвращает (train, dev, сведения). dev — с полем «группа»: здоровье, право, живые, фон."""
    rnd = random.Random(seed)
    lay = jl(os.path.join(ПРОЕКТ, "train/data/queries_lay.jsonl"))
    teach = jl(os.path.join(ПРОЕКТ, "train/data/queries_claude_teacher.jsonl"))
    lex = jl(os.path.join(ПРОЕКТ, "rack/data/lex_questions.jsonl"))
    arts = статьи()
    points = jl(os.path.join(ПРОЕКТ, "train/data/docs_points.jsonl"))
    tops = темы()
    train, dev = [], []
    # здоровье
    h_base = [(q["text"], q["article_no"]) for q in lay if q["split"] == "train"]
    h_base += [(q["text"], q["article_no"]) for q in teach if q["split"] == "train_t"]
    h_docs = [(_join(a["title"], a["criteria"], a.get("notes")), a["article_no"]) for a in arts]
    h_docs += [(_join(p["title"], p["criteria"]), p["article_no"]) for p in points]
    for t, a in h_base + h_docs:
        train.append(строка(t, 1, 0, [a], (), "здоровье"))
    short = [(t.lower().rstrip("."), a) for t, a in h_base if len(t) < 80]
    for _ in range(4000):
        x, a = rnd.choice(short)
        train.append(строка(rnd.choice(FRAMES).format(x=x), 1, 0, [a], (), "здоровье:обёртка"))
    pool_h = h_base + h_docs
    for _ in range(2000):
        t, a = rnd.choice(pool_h)
        train.append(строка(typo(t, rnd), 1, 0, [a], (), "здоровье:опечатки"))
    for _ in range(3000):
        t, a = rnd.choice(h_base)
        train.append(строка(chatter(t, rnd), 1, 0, [a], (), "здоровье:разговор"))
    for q in lay:
        if q["split"] == "dev":
            dev.append(строка(q["text"], 1, 0, [q["article_no"]], (), "lay dev", "здоровье"))
    for q in teach:
        if q["split"] == "dev_t":
            dev.append(строка(q["text"], 1, 0, [q["article_no"]], (), "учитель dev", "здоровье"))
    # право
    l_base = [(q["text"], q["topic_id"], q.get("also_health")) for q in lex if q["split"] == "train"]
    for t, y, ah in l_base:
        train.append(строка(t, None if ah else 0, 1, (), [y], "право"))
    for tp in tops:
        train.append(строка(_join(tp["title"], tp["answer_hint"]), 0, 1, (), [tp["topic_id"]], "право:тема"))
    for _ in range(1500):
        t, y, ah = rnd.choice(l_base)
        train.append(строка(chatter(t, rnd), None if ah else 0, 1, (), [y], "право:разговор"))
    for _ in range(1500):
        t, y, ah = rnd.choice(l_base)
        train.append(строка(typo(t, rnd), None if ah else 0, 1, (), [y], "право:опечатки"))
    for q in lex:
        if q["split"] == "dev":
            dev.append(строка(q["text"], None if q.get("also_health") else 0, 1, (), [q["topic_id"]], "lex dev", "право"))
    # живые пулы
    фильтр = Фильтр(проверочные_тексты())
    live_rows, dropped = живые_пулы(фильтр)
    rnd.shuffle(live_rows)
    cut = int(len(live_rows) * 0.15)
    for r in live_rows[:cut]:
        dev.append(dict(r, группа="живые"))
    for r in live_rows[cut:]:
        train += [r, r]
        for x in live(r["текст"], rnd, 4):
            train.append(dict(r, текст=x, источник=r["источник"] + ":живая копия"))
    # фон
    for t in фон("train", 12000, seed):
        train.append(строка(t, 0, 0, (), (), "фон"))
    for t in фон("dev", 1500, seed):
        dev.append(строка(t, 0, 0, (), (), "фон dev", "фон"))
    сведения = {"train": len(train), "dev": len(dev), "живых_в_пулах": len(live_rows), "живых_dev": cut,
                "выброшено_почти_повторов": dropped, "фон_train": 12000, "фон_dev": 1500}
    return train, dev, сведения


def команды(split):
    """MASSIVE ru (Amazon, CC BY 4.0): голосовые команды — область нового блока «команды»."""
    path = os.path.join(ПРОЕКТ, "science", "data", "cache", "massive_%s.jsonl" % split)
    return [(r["text"], r["label"]) for r in jl(path)]


def метки_команд():
    return json.load(open(os.path.join(ПРОЕКТ, "science", "data", "cache", "massive_labels.json"), encoding="utf-8"))
