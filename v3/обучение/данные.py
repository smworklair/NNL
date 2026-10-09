# -*- coding: utf-8 -*-
"""Источники данных v3 (рабочий проект — только чтение).

Обучение берёт ТОЛЬКО train-части; dev — для ранней остановки; test-части (из них собран измеритель bench) не трогаются.
  здоровье: train/data/queries_lay.jsonl (train), train/data/queries_claude_teacher.jsonl (train_t),
            train/data/docs_articles.jsonl и docs_points.jsonl (официальный текст статей, метка = номер статьи);
            dev = queries_lay (dev).
  право:    rack/data/lex_questions.jsonl (train), rack/data/lex_topics.json (название + краткий ответ темы);
            dev = lex_questions (dev).
"""
import json
import os

ROOT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"
BENCH = r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl"
DOMAINS = ("здоровье", "право")


def _jsonl(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _join(*parts):
    out = []
    for p in parts:
        if isinstance(p, list):
            out.extend(str(x) for x in p)
        elif p:
            out.append(str(p))
    return " ".join(out)


def health_docs():
    rows = [(_join(a["title"], a["criteria"], a.get("notes")), a["article_no"]) for a in _jsonl("train/data/docs_articles.jsonl")]
    rows += [(_join(p["title"], p["criteria"]), p["article_no"]) for p in _jsonl("train/data/docs_points.jsonl")]
    return rows


def law_docs():
    with open(os.path.join(ROOT, "rack/data/lex_topics.json"), encoding="utf-8") as f:
        topics = json.load(f)
    return [(_join(t["title"], t["answer_hint"]), t["topic_id"]) for t in topics]


def health_ids():
    return [a["article_no"] for a in _jsonl("train/data/docs_articles.jsonl")]


def law_ids():
    with open(os.path.join(ROOT, "rack/data/lex_topics.json"), encoding="utf-8") as f:
        return [t["topic_id"] for t in json.load(f)]


def domain_data(domain, split):
    """[(текст, id)] области; split: 'train' (вопросы + документы) или 'dev'."""
    if domain == "здоровье":
        lay = _jsonl("train/data/queries_lay.jsonl")
        if split == "dev":
            return [(q["text"], q["article_no"]) for q in lay if q["split"] == "dev"]
        rows = [(q["text"], q["article_no"]) for q in lay if q["split"] == "train"]
        rows += [(q["text"], q["article_no"]) for q in _jsonl("train/data/queries_claude_teacher.jsonl") if q["split"] == "train_t"]
        return rows + health_docs()
    if domain == "право":
        lex = _jsonl("rack/data/lex_questions.jsonl")
        if split == "dev":
            return [(q["text"], q["topic_id"]) for q in lex if q["split"] == "dev"]
        return [(q["text"], q["topic_id"]) for q in lex if q["split"] == "train"] + law_docs()
    raise ValueError(domain)


def bench():
    with open(BENCH, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]
