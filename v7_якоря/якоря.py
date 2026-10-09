# -*- coding: utf-8 -*-
"""v7, опыт «якоря»: говорят ли разные блоки на одном языке через общий стандарт — фразы-якоря.

Идея (relative representations, Moschella и др., ICLR 2023). У каждого блока свой «язык чисел» (вектор фразы внутри блока).
Ядро задаёт стандарт: N фраз-якорей. Блок описывает любую фразу НЕ своими числами, а «насколько она похожа на каждый якорь»
(косинус между вектором фразы и вектором якоря В ЭТОМ ЖЕ блоке). Получается N чисел с одинаковым смыслом у всех блоков.
Каждый блок сам выравнивает шкалу по якорям (среднее/разброс сходств якорей с якорями) — без меток, только свои числа.
В ядре — только данные (якоря) и арифметика (косинус, среднее, сумма). Ни одного обученного числа.

Блоки (v6, без переобучения): здоровье.прил4 (модель приложения), право.знание2б, право.заявка2, здоровье.заявка3.
Проверка «общего языка»: простой линейный классификатор «здоровье / право / вне» учится на описаниях ОДНОГО блока
и проверяется на описаниях ДРУГОГО блока без переучивания.

КРИТЕРИИ УСПЕХА (записаны ДО первого запуска, Claude, 2026-10-08):
  К1 общий язык: для каждой пары разных блоков (A → B) точность ≥ 0,60 и ≥ 75 % от точности «учил и проверил на B».
  К2 контроль: если у блока B перемешать порядок якорей (стандарт нарушен), точность A → B — не выше доли самого частого класса + 5 п.п.
  К3 организм: среднее описаний всех блоков даёт точность не ниже лучшего одиночного блока.
  К4 Lego: если при проверке убрать из среднего любой один блок, точность падает не больше чем на 5 п.п.
Если К1 не выполнен — общего языка через якоря у этих блоков нет (или нужны другие якоря); это тоже результат.

Данные (только чтение):
  обучение пробы — пул 1 (calm_topic, разметка Claude) + пул 2 (архив Mail.ru, разметка Muse Spark), спорные выброшены;
  проверка — свежие2 (разметка Claude) + свежие3 (разметка Muse Spark), спорные выброшены;
  якоря — случайные вопросы архива Ответов Mail.ru из 4 групп (военная служба, армейские слова в других разделах, болезни, всё прочее),
          без пересечений с данными обучения и проверки.
Ничего вне C:\\ЯДРО-ОПЫТ\\v7_якоря не пишет. Рабочий проект военкомата — только чтение.

Запуск (системный Python, из любой папки):
  python C:\\ЯДРО-ОПЫТ\\v7_якоря\\якоря.py            — полный опыт (N = 1000 якорей)
  python C:\\ЯДРО-ОПЫТ\\v7_якоря\\якоря.py --проба    — быстрая проверка, что всё запускается (200 якорей, мало данных; цифры не смотреть)
Результат: C:\\ЯДРО-ОПЫТ\\v7_якоря\\результат.json и печать таблиц; якоря — якоря.json (sha256 в результате)."""
import argparse
import hashlib
import json
import os
import random
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402

ROOT = r"C:\ЯДРО-ОПЫТ"
V6 = os.path.join(ROOT, "v6")
OUT = os.path.join(ROOT, "v7_якоря")
EXT = os.path.join(ROOT, "внешние")
ARC = os.path.join(ROOT, "данные", "otvetmailru")
sys.path.insert(0, V6)
sys.path.insert(0, os.path.join(V6, "архитектуры"))

import общее as G  # noqa: E402
import текст as T  # noqa: E402

BLOCKS = ["здоровье.прил4", "право.знание2б", "право.заявка2", "здоровье.заявка3"]
AREAS = ["здоровье", "право", "вне"]


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


# ---------------- векторы фраз внутри блоков (их собственный «язык») ----------------
def block_encoder(name):
    d = os.path.join(V6, "блоки", name)
    ps = json.load(open(os.path.join(d, "паспорт.json"), encoding="utf-8"))
    w = os.path.join(d, ps["веса"]["файл"])
    arch = ps["архитектура"]
    if arch == "приложение":
        import приложение as A
        obj = A.load(w, ps, None)
        core_v3 = obj["mods"][1]

        def enc(texts):
            out = []
            for i in range(0, len(texts), 256):
                out.append(np.asarray(core_v3.keys(obj["m"], obj["v"], texts[i:i + 256]), dtype=np.float64))
            return np.vstack(out)
        return enc
    P = G.load_npz(w)
    P.pop("классы", None)
    B = ps["настройки"]["корзины_ответа" if arch == "знание" else "корзины_заявки"]
    emb = P["emb"].astype(np.float64)

    def enc(texts):
        out = np.zeros((len(texts), emb.shape[1]))
        for i, t in enumerate(texts):
            idx = T.features(t, B)
            if idx:
                out[i] = emb[np.asarray(idx, dtype=np.int64)].mean(0)
        return out
    return enc


def unit(X):
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)


class Relative:
    """Описание фраз блока через якоря: косинусы со своими векторами якорей, выровненные по самим якорям."""

    def __init__(self, enc, anchors):
        self.enc = enc
        self.A = unit(enc(anchors))
        S = self.A @ self.A.T                       # якоря против якорей — своя шкала блока, без меток
        self.mu, self.sd = S.mean(0), S.std(0) + 1e-6

    def __call__(self, texts, perm=None):
        R = (unit(self.enc(texts)) @ self.A.T - self.mu) / self.sd
        return R[:, perm] if perm is not None else R


# ---------------- простой линейный классификатор (numpy, без ИИ в ядре — это измерительный прибор) ----------------
def fit(X, y, k, epochs=300, lr=0.5, l2=1e-3, seed=0):
    rng = np.random.RandomState(seed)
    W = rng.normal(0, 0.01, (X.shape[1], k))
    b = np.zeros(k)
    Y = np.eye(k)[y]
    cw = len(y) / (k * np.bincount(y, minlength=k).clip(1))   # классы уравнены по весу
    sw = cw[y][:, None]
    for _ in range(epochs):
        Z = X @ W + b
        Z -= Z.max(1, keepdims=True)
        Pr = np.exp(Z)
        Pr /= Pr.sum(1, keepdims=True)
        Gd = (Pr - Y) * sw / len(y)
        W -= lr * (X.T @ Gd + l2 * W)
        b -= lr * Gd.sum(0)
    return W, b


def acc(model, X, y):
    W, b = model
    return float(((X @ W + b).argmax(1) == y).mean())


# ---------------- данные ----------------
def labeled():
    from обучение import реальные
    p1, _ = реальные.pool()
    tr = [(r["текст"], "право" if r["право"] is not None else "здоровье" if r["здоровье"] is not None else "вне") for r in p1]
    texts2 = json.load(open(os.path.join(V6, "реальные", "архив", "пул2_тексты.json"), encoding="utf-8"))
    tr += [(texts2[r["i"]]["текст"], r["область"]) for r in jl(os.path.join(EXT, "разметка_пул2.jsonl")) if r["область"] != "спорно"]
    te = [(r["вопрос"], r["область"]) for r in jl(os.path.join(V6, "реальные", "архив", "разметка_свежие2.jsonl")) if len(r["области"]) == 1]
    texts3 = json.load(open(os.path.join(V6, "реальные", "архив", "свежие3_тексты.json"), encoding="utf-8"))
    te += [(texts3[r["i"]]["текст"], r["область"]) for r in jl(os.path.join(EXT, "разметка_свежие3.jsonl")) if r["область"] != "спорно"]
    return tr, te


def make_anchors(n, exclude, seed=2026):
    spec = __import__("importlib.util").util.spec_from_file_location("sn", os.path.join(V6, "реальные", "архив", "собрать_наборы.py"))
    sn = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(sn)
    chunks = sorted(os.listdir(os.path.join(ARC, "готово")))[:8]
    rnd = random.Random(seed)
    used = set()
    for f in ("свежие2", "свежие3", "пул2"):
        used |= {r["qid"] for r in json.load(open(os.path.join(V6, "реальные", "архив", f + "_тексты.json"), encoding="utf-8"))}
    out = []
    for group in ("армия", "ключи", "болезни", "фон"):
        rows = []
        for c in chunks:
            rows += [json.loads(l) for l in open(os.path.join(ARC, "куски", c, group + ".jsonl"), encoding="utf-8")]
        rnd.shuffle(rows)
        got = 0
        for r in rows:
            if got >= n // 4:
                break
            t = sn.text(r)
            if len(t) < 15 or r["qid"] in used or t in exclude:
                continue
            out.append({"группа": group, "текст": t})
            got += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--проба", action="store_true")
    a = ap.parse_args()
    n_anchor = 200 if a.проба else 1000
    tr, te = labeled()
    if a.проба:
        tr, te = tr[:300], te[:100]
    anchors = make_anchors(n_anchor, {t for t, _ in tr + te})
    json.dump(anchors, open(os.path.join(OUT, "якоря.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    sha = hashlib.sha256(open(os.path.join(OUT, "якоря.json"), "rb").read()).hexdigest()
    at = [x["текст"] for x in anchors]
    ytr = np.array([AREAS.index(y) for _, y in tr])
    yte = np.array([AREAS.index(y) for _, y in te])
    chance = float(np.bincount(yte, minlength=3).max() / len(yte))
    print("якорей %d (sha256 %s…), обучение пробы %d, проверка %d, доля самого частого класса %.3f" % (len(at), sha[:12], len(tr), len(te), chance), flush=True)

    rel, Xtr, Xte, Xperm = {}, {}, {}, {}
    perm = np.random.RandomState(7).permutation(len(at))
    for b in BLOCKS:
        rel[b] = Relative(block_encoder(b), at)
        Xtr[b] = rel[b]([t for t, _ in tr])
        Xte[b] = rel[b]([t for t, _ in te])
        Xperm[b] = rel[b]([t for t, _ in te], perm)
        print("  блок %-18s описан через якоря" % b, flush=True)
    models = {b: fit(Xtr[b], ytr, 3) for b in BLOCKS}

    M = {A: {B: round(acc(models[A], Xte[B], yte), 4) for B in BLOCKS} for A in BLOCKS}
    C = {A: {B: round(acc(models[A], Xperm[B], yte), 4) for B in BLOCKS if B != A} for A in BLOCKS}
    k1 = all(M[A][B] >= 0.60 and M[A][B] >= 0.75 * M[B][B] for A in BLOCKS for B in BLOCKS if A != B)
    k2 = all(v <= chance + 0.05 for row in C.values() for v in row.values())

    fused = lambda X, bs: np.mean([X[b] for b in bs], axis=0)
    mf = fit(fused(Xtr, BLOCKS), ytr, 3)
    f_all = acc(mf, fused(Xte, BLOCKS), yte)
    best_single = max(M[b][b] for b in BLOCKS)
    loo = {b: round(acc(mf, fused(Xte, [x for x in BLOCKS if x != b]), yte), 4) for b in BLOCKS}
    k3 = f_all >= best_single
    k4 = all(f_all - v <= 0.05 for v in loo.values())

    res = {"проба": a.проба, "якорей": len(at), "якоря_sha256": sha, "обучение_пробы": len(tr), "проверка": len(te),
           "доля_самого_частого_класса": round(chance, 4),
           "учил_на_A_проверил_на_B": M, "контроль_перемешанные_якоря": C,
           "сумма_всех_блоков": round(f_all, 4), "лучший_одиночный": best_single, "без_одного_блока": loo,
           "критерии": {"К1_общий_язык": k1, "К2_контроль": k2, "К3_организм": k3, "К4_Lego": k4}}
    json.dump(res, open(os.path.join(OUT, "результат.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\nточность: строка — на каком блоке учили, столбец — на каком проверили (диагональ — свой блок)")
    print(" " * 20 + "".join("%-18s" % b for b in BLOCKS))
    for A in BLOCKS:
        print("%-20s" % A + "".join("%-18.3f" % M[A][B] for B in BLOCKS))
    print("\nконтроль (якоря у проверяемого блока перемешаны):", json.dumps(C, ensure_ascii=False))
    print("сумма всех блоков %.3f | лучший одиночный %.3f | без одного блока %s" % (f_all, best_single, loo))
    print("\nКРИТЕРИИ:", json.dumps(res["критерии"], ensure_ascii=False))
    if a.проба:
        print("\n(это проба на малых данных — цифры не значат ничего, только проверка запуска)")


if __name__ == "__main__":
    main()
