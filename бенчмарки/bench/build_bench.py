# -*- coding: utf-8 -*-
"""Сборка измерителя NNL (общая для всех вариантов v1/v2/v3).

Берёт ТОЛЬКО held-out вопросы, не используемые в обучении блоков:
- здоровье: train/data/queries_lay.jsonl split==test (статья Расписания -> article_no)
- право:    rack/data/lex_questions.jsonl split==test (правовая тема -> topic_id)

Выход: bench.jsonl, одна строка = один вопрос, поля: вопрос, ответ, область (+qid для прослеживаемости).
Обучение блоков использует только train-сплиты, поэтому пересечений с бенчем нет.
"""
import json, os, random

ROOT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"
OUT = r"C:\ЯДРО-ОПЫТ\бенчмарки\bench\bench.jsonl"

def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def main():
    lay = load_jsonl(os.path.join(ROOT, "train", "data", "queries_lay.jsonl"))
    lay_test = [q for q in lay if q.get("split") == "test"]
    lex = load_jsonl(os.path.join(ROOT, "rack", "data", "lex_questions.jsonl"))
    lex_test = [q for q in lex if q.get("split") == "test"]
    rows = []
    for q in lay_test:
        rows.append({"вопрос": q["text"], "ответ": q["article_no"], "область": "здоровье",
                     "qid": q.get("qid", "")})
    for q in lex_test:
        rows.append({"вопрос": q["text"], "ответ": q["topic_id"], "область": "право",
                     "qid": q.get("text", "")[:0] or ("lex-" + q["topic_id"])})
    rnd = random.Random(7)
    rnd.shuffle(rows)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # проверка отсутствия пересечений с train (по текстам)
    lay_train_texts = set(q["text"] for q in lay if q.get("split") == "train")
    lex_train_texts = set(q["text"] for q in lex if q.get("split") == "train")
    leak = sum(1 for r in rows if r["вопрос"] in lay_train_texts or r["вопрос"] in lex_train_texts)
    print("health_test=%d law_test=%d total=%d leak_with_train=%d" % (len(lay_test), len(lex_test), len(rows), leak))
    print("wrote", OUT)

if __name__ == "__main__":
    main()
