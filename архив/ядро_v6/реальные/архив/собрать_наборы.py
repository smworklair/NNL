# -*- coding: utf-8 -*-
"""Наборы из архива Ответов Mail.ru (its5Q/otvetmailru, CC0; куски aa–ah, отобранные фильтром):
65 % — раздел «Военная служба», 35 % — вопросы других разделов со словами про призыв/армию (там же омонимы: «повестка в суд»).
Текст = заголовок + пояснение (до 350 знаков). Выброшены почти-повторы всех прежних наборов (calm_topic 1500, clean_seeds, общий тест,
зашумлённые) и друг друга. свежие2 — проверка выбора В2/В2б; свежие3 — закрыт до следующего переобучения; пул2 — обучение.
Зерно 7007. Запуск: python собрать_наборы.py"""
import json, os, random, re, sys
sys.stdout.reconfigure(encoding="utf-8")
SRC = r"C:\ЯДРО-ОПЫТ\данные\otvetmailru\куски"
OLD = [r"C:\Users\Admin\Documents\mailru_style\calm_topic.jsonl", r"C:\Users\Admin\Documents\mailru_style\clean_seeds.jsonl",
       r"C:\ЯДРО-ОПЫТ\бенчмарки\bench\bench.jsonl", r"C:\Users\Admin\Documents\mailru_style\noisy_dev.jsonl"]


def text(r):
    t = re.sub(r"\s+", " ", (r["вопрос"] or "").strip())
    d = re.sub(r"\s+", " ", (r["пояснение"] or "").replace("<br>", " ").strip())
    if d and d[:40].lower() != t[:40].lower():
        t = t.rstrip() + (" " if t.endswith(("?", ".", "!")) else ". ") + d
    elif d:
        t = d
    return t[:350]


def grams(t):
    s = " ".join(re.findall(r"[а-яa-z0-9]+", t.lower().replace("ё", "е")))
    return {s[i:i + 5] for i in range(max(1, len(s) - 4))}


def main():
    A, K = [], []
    for c in "abcdefgh":
        A += [json.loads(l) for l in open(os.path.join(SRC, "a" + c, "армия.jsonl"), encoding="utf-8")]
        K += [json.loads(l) for l in open(os.path.join(SRC, "a" + c, "ключи.jsonl"), encoding="utf-8")]
    old = []
    for p in OLD:
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            old.append(r.get("text") or r.get("вопрос"))
    index = {}
    for j, t in enumerate(old):
        for g in grams(t):
            index.setdefault(g, set()).add(j)
    og = [grams(t) for t in old]
    rnd = random.Random(7007)
    rnd.shuffle(A); rnd.shuffle(K)
    seen, out = [], {"свежие2": [], "свежие3": [], "пул2": []}
    need = {"свежие2": (130, 70), "свежие3": (130, 70), "пул2": (650, 350)}
    src = {"армия": iter(A), "ключи": iter(K)}

    def ok(t):
        if len(t) < 12:
            return False
        g = grams(t)
        cand = {}
        for x in g:
            for j in index.get(x, ()):
                cand[j] = cand.get(j, 0) + 1
        if any(c / len(g | og[j]) >= 0.5 for j, c in cand.items()):
            return False
        if any(len(g & h) / len(g | h) >= 0.5 for h in seen):
            return False
        seen.append(g)
        return True

    for name, (na, nk) in need.items():
        for kind, n in (("армия", na), ("ключи", nk)):
            got = 0
            while got < n:
                r = next(src[kind])
                t = text(r)
                if ok(t):
                    out[name].append({"текст": t, "откуда": kind, "кат": r["кат"], "qid": r["qid"]})
                    got += 1
        rnd.shuffle(out[name])
        json.dump(out[name], open(name + "_тексты.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(name, len(out[name]))


if __name__ == "__main__":
    main()
