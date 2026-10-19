# -*- coding: utf-8 -*-
"""Данные блоков v4. Рабочий проект — только чтение. Обучение — только train-части, dev — для остановки,
test-части (измерители) не трогаются.
  здоровье, право — как в v3 (lay+учитель+документы; lex+темы);
  команды — MASSIVE ru (science/data/cache, CC BY 4.0);
  фон — стандарт/фон_*.jsonl (заголовки, отзывы, аннотации)."""
import json
import os

ROOT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"
CACHE = os.path.join(ROOT, "science", "data", "cache")
V4 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _join(*parts):
    out = []
    for p in parts:
        if isinstance(p, list):
            out.extend(str(x) for x in p)
        elif p:
            out.append(str(p))
    return " ".join(out)


def classes(domain):
    if domain == "здоровье":
        return [a["article_no"] for a in _jsonl(os.path.join(ROOT, "train/data/docs_articles.jsonl"))]
    if domain == "право":
        return [t["topic_id"] for t in json.load(open(os.path.join(ROOT, "rack/data/lex_topics.json"), encoding="utf-8"))]
    if domain == "команды":
        return json.load(open(os.path.join(CACHE, "massive_labels.json"), encoding="utf-8"))
    raise ValueError(domain)


def domain_data(domain, split):
    """[(текст, id)]; split: train | dev."""
    if domain == "здоровье":
        lay = _jsonl(os.path.join(ROOT, "train/data/queries_lay.jsonl"))
        if split == "dev":
            return [(q["text"], q["article_no"]) for q in lay if q["split"] == "dev"]
        rows = [(q["text"], q["article_no"]) for q in lay if q["split"] == "train"]
        rows += [(q["text"], q["article_no"]) for q in _jsonl(os.path.join(ROOT, "train/data/queries_claude_teacher.jsonl")) if q["split"] == "train_t"]
        rows += [(_join(a["title"], a["criteria"], a.get("notes")), a["article_no"]) for a in _jsonl(os.path.join(ROOT, "train/data/docs_articles.jsonl"))]
        rows += [(_join(p["title"], p["criteria"]), p["article_no"]) for p in _jsonl(os.path.join(ROOT, "train/data/docs_points.jsonl"))]
        return rows
    if domain == "право":
        lex = _jsonl(os.path.join(ROOT, "rack/data/lex_questions.jsonl"))
        if split == "dev":
            return [(q["text"], q["topic_id"]) for q in lex if q["split"] == "dev"]
        topics = json.load(open(os.path.join(ROOT, "rack/data/lex_topics.json"), encoding="utf-8"))
        return [(q["text"], q["topic_id"]) for q in lex if q["split"] == "train"] + \
               [(_join(t["title"], t["answer_hint"]), t["topic_id"]) for t in topics]
    if domain == "команды":
        return [(r["text"], r["label"]) for r in _jsonl(os.path.join(CACHE, "massive_%s.jsonl" % ("train" if split == "train" else "dev")))]
    raise ValueError(domain)


def background(split, version=1):
    name = "фон_%s.jsonl" % split if version == 1 else "фон%d_%s.jsonl" % (version, split)
    return [r["текст"] for r in _jsonl(os.path.join(V4, "стандарт", name))]
