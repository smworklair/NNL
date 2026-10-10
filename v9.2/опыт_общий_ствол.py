# -*- coding: utf-8 -*-
"""v9.2 опыт: можно ли собрать «один ум» из подключаемых блоков на ОБЩЕМ стволе — в крошечном масштабе.

Устройства (все на одних данных, одних токенах языка v8, одних формулах: мешок токенов → сумма/√n → линейная голова):
  A  «как v8»          у каждого блока свой кодировщик (своя соль, своя таблица), ответы у хозяев.
  B  «ствол, вместе»   один общий кодировщик, одна голова на все ответы, учили сразу вместе.
  C  «ствол, вставка»  ствол и голова здоровья учены на здоровье; ствол ЗАМОРОЖЕН; право вставлено отдельной головой.
  D  «ствол случайный» ствол не учится вообще; головы вставляются по очереди.
  E  «ствол из текста» ствол ПРЕДОБУЧЕН без меток на общем тексте (PPMI+SVD) и заморожен; головы вставляются по очереди.
Что смотрим:
  1. Цена общего ствола: каждая область на своих вопросах (отложенные перефразировки + живые размеченные вопросы).
  2. Вставка без переучивания старого: насколько проседает вставленный блок.
  3. Смесь (кусок про здоровье + кусок про право): оба ответа в общей двойке? двойка из одной области?
  4. Вынули право: здоровье осталось тем же побитово?
Данные: контрольные вопросы блоков v8 (1157, внутри репозитория) + живые размеченные вопросы v6/реальные (только тест);
текст без меток для ствола E: v4/стандарт/фон2_train + пул2/пул3 (из корпуса удалены тексты, совпадающие с тестовыми).
Настоящих стыковых вопросов в репозитории нет (они во внешних файлах), смесь собирается склейкой двух одиночных:
это проверка механики сборки, а не знаний о праве и здоровье."""
import importlib.util
import json
import os
import sys
import zlib

import numpy as np

sys.dont_write_bytecode = True
ЭТА = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЭТА)
V8 = os.path.join(КОРЕНЬ, "v8")
ДАННЫЕ = os.path.join(V8, "блоки", "основная_внешние.з1")
B, D, DT = 12288, 48, 128      # корзины; размер своего ствола; размер предобученного ствола
ЭПОХ = 40

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ------------------------------------------------------------------ данные
def язык():
    spec = importlib.util.spec_from_file_location("v8_ядро_ядро", os.path.join(V8, "ядро", "ядро.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m.Язык(os.path.join(V8, "язык"))


def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def норм(t):
    return " ".join(t.lower().split())


def загрузить(ЯЗ):
    Z, П = jl(os.path.join(ДАННЫЕ, "здоровье", "контроль.jsonl")), jl(os.path.join(ДАННЫЕ, "право", "контроль.jsonl"))
    assert all(a["вопрос"] == b["вопрос"] for a, b in zip(Z, П))
    ответы_з = sorted({x for r in Z for x in r["ответы"]})
    ответы_п = sorted({x for r in П for x in r["ответы"]})
    q = [{"токены": ЯЗ.перевести(a["вопрос"])["токены"], "з": a["ответы"], "п": b["ответы"]} for a, b in zip(Z, П)]
    группы, prev = [], None
    for i, r in enumerate(q):
        k = (tuple(sorted(r["з"])), tuple(sorted(r["п"])))
        if k != prev:
            группы.append([])
            prev = k
        группы[-1].append(i)
    тест = set()
    for g in группы:
        if len(g) >= 3:
            тест.update(g[2::3])       # каждый третий вариант группы перефразировок — в тест
    # живые размеченные вопросы: только тест
    живые, тексты_живых = [], set()
    рас = os.path.join(КОРЕНЬ, "v6", "реальные")
    for f in ("разметка.jsonl", "разметка_свежие.jsonl", "разметка_отложенные.jsonl", os.path.join("архив", "разметка_свежие2.jsonl")):
        for r in jl(os.path.join(рас, f)):
            тексты_живых.add(норм(r["вопрос"]))
            з = ["ответ:здоровье:%s" % a for a in r["ответы"] if "ответ:здоровье:%s" % a in ответы_з]
            п = ["ответ:право:%s" % a for a in r["ответы"] if "ответ:право:%s" % a in ответы_п]
            if з or п:
                живые.append({"токены": ЯЗ.перевести(r["вопрос"])["токены"], "з": з, "п": п})
    return q, ответы_з, ответы_п, sorted(тест), живые, тексты_живых


# ------------------------------------------------------------------ кодировщик
def индексы(соль, токены):
    return np.array([zlib.crc32((соль + "\x1f" + t).encode("utf-8")) % B for t in токены], np.int64)


def плоско(idx_list):
    n = np.array([len(x) for x in idx_list], np.int64)
    flat = np.concatenate(idx_list) if len(idx_list) else np.zeros(0, np.int64)
    return flat, np.repeat(np.arange(len(idx_list)), n), np.sqrt(np.maximum(n, 1)).astype(np.float32)


def признак(E, idx_list):
    flat, rows, sq = плоско(idx_list)
    h = np.zeros((len(idx_list), E.shape[1]), np.float32)
    np.add.at(h, rows, E[flat])
    return h / sq[:, None]


def сигм(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def оценки(E, W, b, idx_list):
    return сигм(признак(E, idx_list) @ W + b)


def учить(E, W, b, idx_list, Y, заморозить_E, rng, lr=0.05):
    """Многометочная логистическая регрессия (Adam), формулы блока v8."""
    E, W, b = E.copy(), W.copy(), b.copy()
    N = len(idx_list)
    m = {k: np.zeros_like(v) for k, v in (("E", E), ("W", W), ("b", b))}
    v = {k: np.zeros_like(x) for k, x in (("E", E), ("W", W), ("b", b))}
    pos_w = np.where(Y.sum(0) > 0, 3.0, 1.0).astype(np.float32)
    t = 0
    for _ in range(ЭПОХ):
        порядок = rng.permutation(N)
        for s in range(0, N, 64):
            ids = порядок[s:s + 64]
            flat, rows, sq = плоско([idx_list[i] for i in ids])
            h = np.zeros((len(ids), E.shape[1]), np.float32)
            np.add.at(h, rows, E[flat])
            h /= sq[:, None]
            p = сигм(h @ W + b)
            y = Y[ids]
            g = ((p - y) * np.where(y > 0, pos_w, 1.0) / len(ids)).astype(np.float32)
            grads = {"W": h.T @ g, "b": g.sum(0)}
            if not заморозить_E:
                gE = np.zeros_like(E)
                np.add.at(gE, flat, ((g @ W.T) / sq[:, None])[rows])
                grads["E"] = gE
            t += 1
            for k, gr in grads.items():
                par = {"E": E, "W": W, "b": b}[k]
                m[k] = 0.9 * m[k] + 0.1 * gr
                v[k] = 0.999 * v[k] + 0.001 * gr * gr
                par -= lr * (m[k] / (1 - 0.9 ** t)) / (np.sqrt(v[k] / (1 - 0.999 ** t)) + 1e-8)
    return E, W, b


def ствол_из_текста(ЯЗ, исключить):
    """E: B×DT. PPMI по совместной встречаемости токенов в окне + усечённое SVD. Меток нет, областей нет."""
    кэш = os.path.join(ЭТА, "_кэш", "ствол_B%d_d%d.npy" % (B, DT))
    if os.path.exists(кэш):
        return np.load(кэш)
    тексты = [r["текст"] for _, r in zip(range(42000), jl(os.path.join(КОРЕНЬ, "v4", "стандарт", "фон2_train.jsonl")))]
    for f in ("пул2_тексты.json", "пул3_тексты.json"):
        for r in json.load(open(os.path.join(КОРЕНЬ, "v6", "реальные", "архив", f), encoding="utf-8")):
            тексты.append(r["текст"])
    тексты = [t for t in тексты if норм(t) not in исключить]
    print("корпус для ствола: %d текстов" % len(тексты), flush=True)
    пары_i, пары_j = [], []
    for t in тексты:
        idx = индексы("общий", ЯЗ.перевести(t)["токены"][:80])
        for sh in range(1, 7):
            if len(idx) > sh:
                пары_i.append(idx[:-sh])
                пары_j.append(idx[sh:])
    i = np.concatenate(пары_i)
    j = np.concatenate(пары_j)
    C = np.bincount(i * B + j, minlength=B * B).astype(np.float32).reshape(B, B)
    C += C.T
    del i, j, пары_i, пары_j
    tot = C.sum()
    ci = C.sum(1)
    cj = ci ** 0.75
    cj = cj / cj.sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        pmi = np.log((C / tot) / (np.outer(ci / tot, cj) + 1e-30) + 1e-30)
    A = np.where(C > 0, np.maximum(pmi, 0), 0).astype(np.float32)
    del C, pmi
    rng = np.random.default_rng(0)
    Q = rng.standard_normal((B, DT + 16)).astype(np.float32)
    for _ in range(4):
        Q, _ = np.linalg.qr(A @ Q)
    Ub, S, _ = np.linalg.svd((Q.T @ A @ Q), full_matrices=False)
    E = (Q @ Ub[:, :DT]) * np.sqrt(S[:DT])[None, :]
    E = (E / (np.linalg.norm(E, axis=1).mean() + 1e-9)).astype(np.float32)
    os.makedirs(os.path.dirname(кэш), exist_ok=True)
    np.save(кэш, E)
    return E


# ------------------------------------------------------------------ один прогон
def один_прогон(q, ответы_з, ответы_п, тест, живые, E_ствол, seed):
    rng = np.random.default_rng(seed)
    nз, nп = len(ответы_з), len(ответы_п)
    tset = set(тест)
    учебные = [i for i in range(len(q)) if i not in tset]
    Yз = np.zeros((len(q), nз), np.float32)
    Yп = np.zeros((len(q), nп), np.float32)
    for i, r in enumerate(q):
        for a in r["з"]:
            Yз[i, ответы_з.index(a)] = 1
        for a in r["п"]:
            Yп[i, ответы_п.index(a)] = 1
    Yобщ = np.concatenate([Yз, Yп], 1)

    def init(соль, n, d=D):
        r = np.random.default_rng(zlib.crc32(соль.encode()) + seed)
        return (r.standard_normal((B, d)) * 0.1).astype(np.float32), np.zeros((d, n), np.float32), np.zeros(n, np.float32)

    def ид_для(токены_список, соль):
        return [индексы(соль, t) for t in токены_список]

    токены_q = [r["токены"] for r in q]
    ид = {с: ид_для(токены_q, с) for с in ("здоровье", "право", "общий")}
    tr = lambda с: [ид[с][i] for i in учебные]

    # компоненты арма: список (соль, E, W, b); выход = склейка оценок компонентов (здоровье | право)
    арм = {}
    Ez, Wz, bz = init("здоровье", nз)
    Ez, Wz, bz = учить(Ez, Wz, bz, tr("здоровье"), Yз[учебные], False, rng)
    Ep, Wp, bp = init("право", nп)
    Ep, Wp, bp = учить(Ep, Wp, bp, tr("право"), Yп[учебные], False, rng)
    арм["A как v8 (свои кодировщики)"] = [("здоровье", Ez, Wz, bz), ("право", Ep, Wp, bp)]

    Eb, Wb, bb = init("общий", nз + nп)
    Eb, Wb, bb = учить(Eb, Wb, bb, tr("общий"), Yобщ[учебные], False, rng)
    арм["B ствол, учили вместе"] = [("общий", Eb, Wb, bb)]

    Ec, Wcз, bcз = init("общий", nз)
    Ec, Wcз, bcз = учить(Ec, Wcз, bcз, tr("общий"), Yз[учебные], False, rng)
    _, Wcп, bcп = init("общий", nп)
    _, Wcп, bcп = учить(Ec, Wcп, bcп, tr("общий"), Yп[учебные], True, rng)
    арм["C ствол (учен на здоровье) заморожен, право вставлено"] = [("общий", Ec, Wcз, bcз), ("общий", Ec, Wcп, bcп)]

    Ed, Wdз, bdз = init("общий", nз)
    _, Wdз, bdз = учить(Ed, Wdз, bdз, tr("общий"), Yз[учебные], True, rng)
    _, Wdп, bdп = init("общий", nп)
    _, Wdп, bdп = учить(Ed, Wdп, bdп, tr("общий"), Yп[учебные], True, rng)
    арм["D ствол случайный, головы вставляются"] = [("общий", Ed, Wdз, bdз), ("общий", Ed, Wdп, bdп)]

    _, Wез, bез = init("общий", nз, DT)
    _, Wеп, bеп = init("общий", nп, DT)
    _, Wез, bез = учить(E_ствол, Wез, bез, tr("общий"), Yз[учебные], True, rng, lr=0.02)
    _, Wеп, bеп = учить(E_ствол, Wеп, bеп, tr("общий"), Yп[учебные], True, rng, lr=0.02)
    арм["E ствол из текста (без меток) заморожен, головы вставляются"] = [("общий", E_ствол, Wез, bез), ("общий", E_ствол, Wеп, bеп)]

    def выход(комп, ids_по_соли):
        return np.concatenate([оценки(E, W, b, ids_по_соли[с]) for с, E, W, b in комп], 1)

    # ---- тесты ----
    з_т = [i for i in тест if q[i]["з"]]
    п_т = [i for i in тест if q[i]["п"]]
    живые_з = [r for r in живые if r["з"]]
    живые_п = [r for r in живые if r["п"]]
    пары = [(a, b) for a in з_т for b in п_т]
    rp = np.random.default_rng(seed + 100)
    пары = [пары[j] for j in rp.choice(len(пары), size=min(300, len(пары)), replace=False)]
    смесь_токены = [токены_q[a] + токены_q[b] for a, b in пары]

    def наборы(токены_список):
        return {с: ид_для(токены_список, с) for с in ("здоровье", "право", "общий")}

    N_з, N_п = наборы([токены_q[i] for i in з_т]), наборы([токены_q[i] for i in п_т])
    Ж_з, Ж_п = наборы([r["токены"] for r in живые_з]), наборы([r["токены"] for r in живые_п])
    N_с = наборы(смесь_токены)

    итог = {}
    for имя, комп in арм.items():
        def top1(P, лист, смещ, ответы, ключ):
            return float(np.mean([ответы[t] in r[ключ] for t, r in zip(P[:, смещ:смещ + len(ответы)].argmax(1), лист)]))
        res = {"здоровье_перефраз": top1(выход(комп, N_з), [q[i] for i in з_т], 0, ответы_з, "з"),
               "право_перефраз": top1(выход(комп, N_п), [q[i] for i in п_т], nз, ответы_п, "п"),
               "здоровье_живые": top1(выход(комп, Ж_з), живые_з, 0, ответы_з, "з"),
               "право_живые": top1(выход(комп, Ж_п), живые_п, nз, ответы_п, "п")}
        PM = выход(комп, N_с)
        оба = одна = 0
        для_з = для_п = 0
        for k, (a, b) in enumerate(пары):
            top2 = np.argsort(-PM[k])[:2]
            из_з = [t for t in top2 if t < nз]
            из_п = [t - nз for t in top2 if t >= nз]
            оба += any(ответы_з[t] in q[a]["з"] for t in из_з) and any(ответы_п[t] in q[b]["п"] for t in из_п)
            одна += (len(из_з) == 2 or len(из_п) == 2)
            для_з += ответы_з[int(PM[k, :nз].argmax())] in q[a]["з"]
            для_п += ответы_п[int(PM[k, nз:].argmax())] in q[b]["п"]
        res.update({"смесь_здоровье_топ1_в_своей_области": для_з / len(пары), "смесь_право_топ1_в_своей_области": для_п / len(пары),
                    "смесь_оба_в_общей_двойке": оба / len(пары), "смесь_двойка_из_одной_области": одна / len(пары)})
        итог[имя] = res
    # вынули право из C, D, E: здоровье осталось тем же?
    сравн = {}
    for имя in ("C ствол (учен на здоровье) заморожен, право вставлено", "D ствол случайный, головы вставляются",
                "E ствол из текста (без меток) заморожен, головы вставляются"):
        комп = арм[имя]
        до = выход(комп, N_з)[:, :nз]
        с, E, W, b = комп[0]
        сравн[имя[0]] = bool(np.array_equal(до, оценки(E, W, b, N_з[с])))
    итог["_вынули_право_здоровье_побитово_то_же"] = сравн
    итог["_счёт"] = {"учебных": len(учебные), "перефраз_здоровье": len(з_т), "перефраз_право": len(п_т), "живых_здоровье": len(живые_з),
                     "живых_право": len(живые_п), "пар_смесь": len(пары)}
    return итог


def main():
    ЯЗ = язык()
    q, ответы_з, ответы_п, тест, живые, тексты_живых = загрузить(ЯЗ)
    print("вопросов %d, ответов здоровья %d, права %d, перефраз в тесте %d, живых размеченных %d" % (
        len(q), len(ответы_з), len(ответы_п), len(тест), len(живые)), flush=True)
    E_ствол = ствол_из_текста(ЯЗ, тексты_живых)
    seeds = [1, 2, 3]
    все = []
    for s in seeds:
        все.append(один_прогон(q, ответы_з, ответы_п, тест, живые, E_ствол, s))
        print("зерно", s, "готово", flush=True)
    сводка = {}
    for имя in все[0]:
        if имя.startswith("_"):
            continue
        сводка[имя] = {}
        for м in все[0][имя]:
            xs = [r[имя][м] for r in все]
            сводка[имя][м] = "%.3f (%.3f–%.3f)" % (np.mean(xs), min(xs), max(xs))
    сводка["_вынули_право_здоровье_побитово_то_же"] = [r["_вынули_право_здоровье_побитово_то_же"] for r in все]
    сводка["_счёт"] = все[0]["_счёт"]
    out = os.path.join(ЭТА, "результаты")
    os.makedirs(out, exist_ok=True)
    json.dump({"зёрна": seeds, "сводка": сводка, "по_зёрнам": все}, open(os.path.join(out, "опыт_общий_ствол.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(сводка, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
