# -*- coding: utf-8 -*-
"""Обучение двух блоков-специалистов v1 (маленькие цельные MLP, numpy, с нуля).

- блок zdorovie: только материал своей области (lay_train + teacher train_t), 88 статей.
- блок pravo: только материал своей области (lex train), 44 темы.
- Блоки обучаются отдельно, ничего не знают друг о друге (разные словари, разные веса).
- Архитектура: Bag-of-words -> Linear -> ReLU -> Linear -> softmax (код архитектуры — обычный код).
- Веса сохраняются в блоки/ИМЯ/weights.npz; рядом vocab.json, knowledge.json, passport.json.
- Маркеры для маршрута ядра извлекаются ТОЛЬКО из заголовков баз знаний (не из вопросов),
  правилом разности множеств — это не обученный классификатор.
"""
import json
import os
import re
import sys
import collections
import numpy as np

sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\v1\ядро")
from kernel import токены, стемы

ROOT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"
VBLOK = r"C:\ЯДРО-ОПЫТ\v1\блоки"
SEED = 42


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def build_knowledge_health():
    docs = load_jsonl(os.path.join(ROOT, "train", "data", "docs_articles.jsonl"))
    kn = {}
    for d in docs:
        a = d["article_no"]
        title = (d.get("title") or "").rstrip(":")
        crit = d.get("criteria") or []
        notes = d.get("notes") or []
        quotes = ["Статья %s. %s" % (a, title)]
        if crit:
            quotes.append("Пункты статьи %s: %s" % (a, "; ".join(crit)))
        cover = [t for t in notes if "редусматр" in t]
        if cover:
            quotes.append(cover[0])
        kn[a] = {"заголовок": title, "цитаты": quotes}
    titles = {a: v["заголовок"] for a, v in kn.items()}
    return kn, titles


def build_knowledge_law():
    tops = json.load(open(os.path.join(ROOT, "rack", "data", "lex_topics.json"), encoding="utf-8"))
    prov_rows = load_jsonl(os.path.join(ROOT, "db", "provisions_v3.jsonl"))
    prov = {p["id"]: p for p in prov_rows}
    kn = {}
    for t in tops:
        qs = []
        for pid in t.get("provision_ids", []):
            p = prov.get(pid)
            if not p or p.get("repealed"):
                continue
            txt = p.get("text_verbatim") or ""
            if len(txt) > 600:
                txt = txt[:600].rsplit(" ", 1)[0] + " […]"
            qs.append(txt)
        kn[t["topic_id"]] = {"заголовок": t["title"], "цитаты": qs[:3]}
    titles = {k: v["заголовок"] for k, v in kn.items()}
    return kn, titles


def stems_of(text):
    return стемы(токены(text))


def extract_markers(kn_h, kn_l, topn=1000):
    """Правило без обучения: стемы из текстов баз знаний (не из вопросов).

    Здоровье: заголовок статьи + ВСЕ пункты + ВСЕ пояснения (сырые тексты базы).
    Право: заголовок темы + заголовки норм + начала текстов норм.
    Маркер = стем, встреченный минимум в 2 документах своей области
    и ни разу в документах чужой области. Разность множеств, не классификатор.
    Источник — только база знаний; вопросы (train/dev/bench) не используются.
    """
    import collections
    dh, dl = collections.Counter(), collections.Counter()
    h_docs = load_jsonl(os.path.join(ROOT, "train", "data", "docs_articles.jsonl"))
    for d in h_docs:
        t = (d.get("title") or "") + " " + " ".join(d.get("criteria") or []) \
            + " " + " ".join(d.get("notes") or [])
        for w in set(stems_of(t)):
            dh[w] += 1
    tops = json.load(open(os.path.join(ROOT, "rack", "data", "lex_topics.json"), encoding="utf-8"))
    prov = {p["id"]: p for p in load_jsonl(os.path.join(ROOT, "db", "provisions_v3.jsonl"))}
    for t in tops:
        s = t.get("title", "")
        for pid in (t.get("provision_ids") or [])[:4]:
            p = prov.get(pid)
            if p and not p.get("repealed"):
                s += " " + (p.get("heading") or "") + " " + ((p.get("text_verbatim") or "")[:400])
        for w in set(stems_of(s)):
            dl[w] += 1
    mh = [w for w, c in dh.most_common() if c >= 2 and dl.get(w, 0) == 0 and len(w) > 3][:topn]
    ml = [w for w, c in dl.most_common() if c >= 2 and dh.get(w, 0) == 0 and len(w) > 3][:topn]
    return mh, ml


def build_vocab(texts, n):
    c = collections.Counter()
    for t in texts:
        for w in stems_of(t):
            c[w] += 1
    words = [w for w, k in c.most_common(n) if k >= 2 and len(w) > 1]
    return {"слова": words}


def train_mlp(X, Y, hidden=128, epochs=40, batch=64, lr=0.01, seed=0):
    rng = np.random.RandomState(seed)
    n, V = X.shape
    C = Y.shape[1]
    W1 = (rng.randn(V, hidden) * np.sqrt(2.0 / V)).astype(np.float64)
    b1 = np.zeros(hidden, dtype=np.float64)
    W2 = (rng.randn(hidden, C) * np.sqrt(2.0 / hidden)).astype(np.float64)
    b2 = np.zeros(C, dtype=np.float64)
    params = [W1, b1, W2, b2]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    b1_, b2_, eps = 0.9, 0.999, 1e-8
    t = 0
    for ep in range(epochs):
        perm = rng.permutation(n)
        tot = 0.0
        for i in range(0, n, batch):
            t += 1
            idx = perm[i:i + batch]
            xb, yb = X[idx], Y[idx]
            B = len(idx)
            h = xb @ W1 + b1
            hr = np.maximum(h, 0)
            z = hr @ W2 + b2
            z -= z.max(axis=1, keepdims=True)
            e = np.exp(z)
            p = e / e.sum(axis=1, keepdims=True)
            loss = -np.sum(yb * np.log(p + 1e-12)) / B
            tot += loss * B
            dz = (p - yb) / B
            dW2 = hr.T @ dz
            db2 = dz.sum(axis=0)
            dh = dz @ W2.T
            dh[h <= 0] = 0
            dW1 = xb.T @ dh
            db1 = dh.sum(axis=0)
            for k, g in enumerate([dW1, db1, dW2, db2]):
                m[k] = b1_ * m[k] + (1 - b1_) * g
                v[k] = b2_ * v[k] + (1 - b2_) * (g * g)
                mh = m[k] / (1 - b1_ ** t)
                vh = v[k] / (1 - b2_ ** t)
                params[k] -= lr * mh / (np.sqrt(vh) + eps)
            W1, b1, W2, b2 = params
        if (ep + 1) % 10 == 0 or ep == 0:
            print("  epoch %d/%d loss=%.4f" % (ep + 1, epochs, tot / n))
    return (W1.astype(np.float32), b1.astype(np.float32),
            W2.astype(np.float32), b2.astype(np.float32))


def bow_matrix(texts, word2id):
    X = np.zeros((len(texts), len(word2id)), dtype=np.float32)
    for i, t in enumerate(texts):
        for w in stems_of(t):
            j = word2id.get(w)
            if j is not None:
                X[i, j] += 1.0
    return X


def main():
    np.random.seed(SEED)
    kn_h, titles_h = build_knowledge_health()
    kn_l, titles_l = build_knowledge_law()
    mh, ml = extract_markers(kn_h, kn_l)
    print("markers health=%d law=%d" % (len(mh), len(ml)))

    # --- данные ТОЛЬКО train-сплитов ---
    lay = load_jsonl(os.path.join(ROOT, "train", "data", "queries_lay.jsonl"))
    teach = load_jsonl(os.path.join(ROOT, "train", "data", "queries_claude_teacher.jsonl"))
    h_train = [q for q in lay if q.get("split") == "train"] + \
              [q for q in teach if q.get("split") == "train_t"]
    lex = load_jsonl(os.path.join(ROOT, "rack", "data", "lex_questions.jsonl"))
    l_train = [q for q in lex if q.get("split") == "train"]
    print("health train=%d law train=%d" % (len(h_train), len(l_train)))

    # --- блок здоровье ---
    h_labels = sorted(set(q["article_no"] for q in h_train))
    h_vocab = build_vocab([q["text"] for q in h_train], 4000)
    h_w2i = {w: i for i, w in enumerate(h_vocab["слова"])}
    Xh = bow_matrix([q["text"] for q in h_train], h_w2i)
    li = {a: i for i, a in enumerate(h_labels)}
    Yh = np.zeros((len(h_train), len(h_labels)), dtype=np.float32)
    for i, q in enumerate(h_train):
        Yh[i, li[q["article_no"]]] = 1.0
    print("train zdorovie: X=%s C=%d params~%d" % (
        Xh.shape, len(h_labels), len(h_w2i) * 128 + 128 * len(h_labels)))
    W1, b1, W2, b2 = train_mlp(Xh, Yh, hidden=128, epochs=40, batch=64, lr=0.01, seed=1)
    dh = os.path.join(VBLOK, "zdorovie")
    os.makedirs(dh, exist_ok=True)
    np.savez_compressed(os.path.join(dh, "weights.npz"), W1=W1, b1=b1, W2=W2, b2=b2)
    json.dump(h_vocab, open(os.path.join(dh, "vocab.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(kn_h, open(os.path.join(dh, "knowledge.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({
        "имя": "zdorovie", "область": "здоровье",
        "тип_входа": "текст.вопрос:str", "тип_выхода": "метка.статья:str",
        "зависимости": "нет (цельная модель, общей основы нет)",
        "чем_обучен": "MLP мешок-слов 4000-128-88, numpy Adam 40 эпох, с нуля, seed=1",
        "на_чём_обучен": "lay_train (2607) + teacher train_t (1104), без dev/test, без данных права",
        "метки": h_labels, "маркеры": mh, "порог": 0.30,
    }, open(os.path.join(dh, "passport.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved zdorovie")

    # --- блок право ---
    l_labels = sorted(set(q["topic_id"] for q in l_train))
    l_vocab = build_vocab([q["text"] for q in l_train], 3000)
    l_w2i = {w: i for i, w in enumerate(l_vocab["слова"])}
    Xl = bow_matrix([q["text"] for q in l_train], l_w2i)
    lj = {a: i for i, a in enumerate(l_labels)}
    Yl = np.zeros((len(l_train), len(l_labels)), dtype=np.float32)
    for i, q in enumerate(l_train):
        Yl[i, lj[q["topic_id"]]] = 1.0
    print("train pravo: X=%s C=%d params~%d" % (
        Xl.shape, len(l_labels), len(l_w2i) * 128 + 128 * len(l_labels)))
    V1, c1, V2, c2 = train_mlp(Xl, Yl, hidden=128, epochs=80, batch=32, lr=0.01, seed=2)
    dl = os.path.join(VBLOK, "pravo")
    os.makedirs(dl, exist_ok=True)
    np.savez_compressed(os.path.join(dl, "weights.npz"), W1=V1, b1=c1, W2=V2, b2=c2)
    json.dump(l_vocab, open(os.path.join(dl, "vocab.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(kn_l, open(os.path.join(dl, "knowledge.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({
        "имя": "pravo", "область": "право",
        "тип_входа": "текст.вопрос:str", "тип_выхода": "метка.тема:str",
        "зависимости": "нет (цельная модель, общей основы нет)",
        "чем_обучен": "MLP мешок-слов 3000-128-44, numpy Adam 80 эпох, с нуля, seed=2",
        "на_чём_обучен": "lex train (920), без dev/test, без данных здоровья",
        "метки": l_labels, "маркеры": ml, "порог": 0.30,
    }, open(os.path.join(dl, "passport.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved pravo")
    print("DONE")


if __name__ == "__main__":
    main()
