# -*- coding: utf-8 -*-
"""Стандарт фона v2 для заявок блоков: «всё, что люди пишут вообще». Фиксируется до обучения блоков.
  headline, reviews, grnti (science/data/cache) — по 4000 train / 1000 dev, как фон v1;
  Яндекс Кью (its5Q/yandex-q, CC0) — заголовки вопросов из первых 40 МБ full.jsonl.gz: 15000 train / 3000 dev;
  Tatoeba (rus_sentences, CC BY 2.0 FR) — короткие бытовые фразы: 15000 train / 3000 dev.
Из Кью убраны вопросы о призыве (слова ниже): это тема блоков права/здоровья, в фоне ей не место."""
import bz2, gzip, hashlib, json, os, re, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "данные", "фон_src")
CACHE = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ\science\data\cache"
CONSCRIPT = re.compile(r"призыв|военкомат|\bарми|отсрочк|повестк|срочн\w* служб|годност|\bгоден|медкомисс|военн\w* билет|военн\w* учет|военн\w* учёт", re.I)

def md5(s): return hashlib.md5(s.encode("utf-8")).hexdigest()
def take(texts, n_tr, n_dv):
    texts = sorted(set(t.strip() for t in texts if len(t.strip()) >= 3), key=md5)
    return texts[:n_tr], texts[n_tr:n_tr + n_dv]

def main():
    out = {"train": [], "dev": []}
    for src in ("headline", "reviews", "grnti"):
        for split, n in (("train", 4000), ("dev", 1000)):
            rows = [json.loads(l)["text"] for l in open(os.path.join(CACHE, "%s_%s.jsonl" % (src, split)), encoding="utf-8")]
            out[split] += [{"текст": t, "источник": src} for t in sorted(rows, key=md5)[:n]]
    yq = []
    with gzip.open(os.path.join(SRC, "yq_part.gz"), "rt", encoding="utf-8") as f:
        try:
            for l in f:
                try:
                    d = json.loads(l)
                except ValueError:
                    continue
                t = d.get("title") or ""
                if t and not CONSCRIPT.search(t + " " + " ".join(d.get("tags") or [])):
                    yq.append(t)
        except (EOFError, zlib.error, OSError):
            pass
    tr, dv = take(yq, 15000, 3000)
    out["train"] += [{"текст": t, "источник": "yandex-q"} for t in tr]
    out["dev"] += [{"текст": t, "источник": "yandex-q"} for t in dv]
    with bz2.open(os.path.join(SRC, "rus_sentences.tsv.bz2"), "rt", encoding="utf-8") as f:
        ta = [l.rstrip("\n").split("\t")[2] for l in f if l.count("\t") >= 2]
    ta = [t for t in ta if not CONSCRIPT.search(t)]
    tr, dv = take(ta, 15000, 3000)
    out["train"] += [{"текст": t, "источник": "tatoeba"} for t in tr]
    out["dev"] += [{"текст": t, "источник": "tatoeba"} for t in dv]
    for split, rows in out.items():
        p = os.path.join(HERE, "фон2_%s.jsonl" % split)
        with open(p, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(p, len(rows), hashlib.sha256(open(p, "rb").read()).hexdigest()[:16], "вопросов Кью всего:", len(yq))

if __name__ == "__main__":
    main()
