# -*- coding: utf-8 -*-
"""v6, шаг «5000 живых вопросов»: заявки права и здоровья + знание права на трёх чистых пулах.
Пул 1 — 1180 calm_topic (Claude), пул 2 — 1000 архива (Muse Spark), пул 3 — 3000 архива (Claude Cowork, сверка с Claude на свежие2 — 189/200).
Спорные не идут. Почти-повторы всех проверочных наборов (вкл. свежие2/3/4, фразы, флагманский 600) выброшены. 15 % пулов — dev.
Калибровка заявки (новое): порог τ — наименьший, при котором на dev чужих выше порога не больше 10 %; если при этом своих выше
порога меньше 90 % — τ опускается до 10 %-квантиля своих. Свои и чужие dev — только живые вопросы пулов.
Один вариант, без подбора по проверочным наборам. Запуск: python обучение/обучить_пул3.py
→ блоки/право.заявка5, здоровье.заявка6, право.знание4"""
import datetime
import json
import os
import random
import sys

import numpy as np

V6 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V6)
sys.path.insert(0, os.path.join(V6, "архитектуры"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from ядро.схема import Types, sha256_file  # noqa: E402
from обучение import данные, реальные  # noqa: E402
from обучение.обучить_заявку_здоровья import FRAMES, chatter, typo  # noqa: E402
from обучение.обучить_право import CFG_A, live, unthrottle  # noqa: E402
from обучение.обучить_заявки_архив import CFG, split  # noqa: E402
from обучение.обучить_чистое import pool2  # noqa: E402
import общее as G  # noqa: E402
import текст as T  # noqa: E402
import знание as Z  # noqa: E402

EXT = r"C:\ЯДРО-ОПЫТ\внешние"
SETS = os.path.join(V6, "реальные", "архив")


def pool3():
    texts = json.load(open(os.path.join(SETS, "пул3_тексты.json"), encoding="utf-8"))
    tests = реальные.test_texts()
    for n in ("свежие2", "свежие3", "свежие4"):
        tests += [r["текст"] for r in json.load(open(os.path.join(SETS, n + "_тексты.json"), encoding="utf-8"))]
    tests += [json.loads(l)["текст"] for l in open(os.path.join(EXT, "фразы.jsonl"), encoding="utf-8")]
    fl = r"C:\ЯДРО-ОПЫТ\бенчмарки\флагманы\набор\набор.jsonl"
    if os.path.exists(fl):
        tests += [json.loads(l)["текст"] for l in open(fl, encoding="utf-8") if l.strip()]
    tg = [реальные._grams(t) for t in tests]
    index = {}
    for j, g in enumerate(tg):
        for x in g:
            index.setdefault(x, []).append(j)
    rows, dropped = [], 0
    for l in open(os.path.join(EXT, "cowork_пул3.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        if r["область"] == "спорно":
            continue
        t = texts[r["i"]]["текст"]
        g = реальные._grams(t)
        hits = {}
        for x in g:
            for j in index.get(x, ()):
                hits[j] = hits.get(j, 0) + 1
        if any(c / len(g | tg[j]) >= 0.5 for j, c in hits.items()):
            dropped += 1
            continue
        rows.append({"текст": t, "право": r["ответы"] if r["область"] == "право" else None,
                     "здоровье": r["ответы"] if r["область"] == "здоровье" else None})
    return rows, dropped


def calibrate(p, own, foreign):
    po, pf = np.array([p(t) for t in own]), np.array([p(t) for t in foreign])
    tau = 0.01
    for c in sorted(set(np.round(pf, 6))):
        if (pf >= c).mean() <= 0.10:
            tau = float(c)
            break
    else:
        tau = float(pf.max()) + 1e-6
    if (po >= tau).mean() < 0.90:
        tau = float(np.quantile(po, 0.10))
    tau = float(min(0.99, max(0.01, tau)))
    return tau, "%d/%d" % ((po >= tau).sum(), len(po)), "%d/%d" % ((pf >= tau).sum(), len(pf))


def train_claim(name, area, pos, neg, own_dev, foreign_dev, info):
    B = CFG["корзины_заявки"]
    rnd = random.Random(3)
    ptr, pdv = split(pos, rnd)
    ntr, ndv = split(neg, rnd)
    ztr = [(T.features(t, B), 1) for t in ptr] + [(T.features(t, B), 0) for t in ntr]
    zdv = [(T.features(t, B), 1) for t in pdv] + [(T.features(t, B), 0) for t in ndv]
    cnt = np.bincount([y for _, y in ztr], minlength=2)
    PZ, log = G.train_bag(B, 2, ztr, zdv, dict(CFG["обучение_заявки"], seed=1), class_weight=(len(ztr) / (2 * cnt)).tolist(), log_prefix=name)
    p = lambda t: float(G.forward(PZ, T.features(t, B))[1])
    tau, own_ok, foreign_ok = calibrate(p, own_dev, foreign_dev)
    fon = данные.background("dev", 2)
    fon_above = sum(p(t) >= tau for t in fon) / len(fon)
    out = os.path.join(V6, "блоки", name)
    os.makedirs(out, exist_ok=True)
    w = os.path.join(out, "веса.npz")
    G.save_npz(w, PZ)
    ty = Types(os.path.join(V6, "типы"))
    ps = {"имя": name, "версия": 1, "область": area, "заявка": True,
          "роль": "знает, какие вопросы — области «%s»; учена на ~5000 живых вопросах с чистой разметкой; порог — по доле чужих" % area,
          "вход": {"тип": "общие:Запрос"}, "выход": {"тип": "общие:Направление", "условие": {"область": area}},
          "архитектура": "заявка", "настройки": dict(CFG, порог_калибровки=tau),
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": int(sum(v.size for v in PZ.values()))},
          "типы": {"общие:Запрос": ty.fingerprint("общие:Запрос"), "общие:Направление": ty.fingerprint("общие:Направление")},
          "обучение": dict(info, скрипт="обучение/обучить_пул3.py", когда=datetime.datetime.now().isoformat(timespec="seconds"),
                           моё=len(ptr), не_моё=len(ntr), dev=log["лучший_dev"], порог=round(tau, 6),
                           калибровка="не больше 10 % чужих dev выше порога, своих не меньше 90 %",
                           свои_dev_выше=own_ok, чужие_dev_выше=foreign_ok, фон_dev_выше=round(fon_above, 4))}
    json.dump(ps, open(os.path.join(out, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("записан", out, json.dumps(ps["обучение"], ensure_ascii=False), flush=True)


def main(only_knowledge="--знание" in sys.argv):
    unthrottle()
    rnd = random.Random(1)
    p1, _ = реальные.pool()
    p2, d2 = pool2()
    p3, d3 = pool3()
    rows = p1 + p2 + p3
    rnd.shuffle(rows)
    cut = int(len(rows) * 0.15)
    dev, tr = rows[:cut], rows[cut:]
    law = lambda rs: [r for r in rs if r["право"] is not None]
    nolaw = lambda rs: [r for r in rs if r["право"] is None]
    hl = lambda rs: [r for r in rs if r["здоровье"] is not None]
    nohl = lambda rs: [r for r in rs if r["здоровье"] is None]
    info = {"пул1": len(p1), "пул2": len(p2), "пул3": len(p3), "выброшено_почти_повторов": d2 + d3, "dev": len(dev),
            "право_живых": len(law(tr)), "здоровье_живых": len(hl(tr)), "данные": "пул1 (Claude) + пул2 (Muse Spark) + пул3 (Claude Cowork)"}
    print(info, flush=True)
    bg = данные.background("train", 2)
    lex_tr, lex_dv = данные.domain_data("право", "train"), данные.domain_data("право", "dev")

    pos = [t for t, _ in lex_tr] + [chatter(rnd.choice(lex_tr)[0], rnd) for _ in range(1500)] + [typo(rnd.choice(lex_tr)[0], rnd) for _ in range(1500)]
    for r in law(tr):
        pos += [r["текст"]] * 2 + live(r["текст"], rnd, 4)
    neg = list(bg)
    for r in nolaw(tr):
        neg += [r["текст"]] * 2 + live(r["текст"], rnd, 3)
    if not only_knowledge: train_claim("право.заявка5", "право", pos, neg, [r["текст"] for r in law(dev)], [r["текст"] for r in nolaw(dev)], info)

    base = [t for t, _ in данные.domain_data("здоровье", "train")]
    short = [t.lower().rstrip(".") for t in base if len(t) < 80]
    framed = [rnd.choice(FRAMES).format(x=rnd.choice(short)) for _ in range(8000)]
    noisy = [typo(rnd.choice(base + framed), rnd) for _ in range(4000)]
    chat = [chatter(rnd.choice(base + framed + noisy), rnd) for _ in range(6000)]
    pos = base + framed + noisy + chat
    for r in hl(tr):
        pos += [r["текст"]] * 2 + live(r["текст"], rnd, 6)
    neg = list(bg)
    for r in nohl(tr):
        neg += [r["текст"]] * 2 + live(r["текст"], rnd, 2)
    if not only_knowledge: train_claim("здоровье.заявка6", "здоровье", pos, neg, [r["текст"] for r in hl(dev)], [r["текст"] for r in nohl(dev)], info)

    classes = данные.classes("право")
    ci = {c: i for i, c in enumerate(classes)}
    BA = CFG_A["корзины_ответа"]
    trA = list(lex_tr)
    for r in law(tr):
        for y in [y for y in r["право"] if y in ci]:      # у разметчиков встречается номер статьи болезни в правовом вопросе — не тема
            trA += [(r["текст"], y)] * 2 + [(x, y) for x in live(r["текст"], rnd, 3)]
    dvA = list(lex_dv) + [(r["текст"], [y for y in r["право"] if y in ci][0]) for r in law(dev) if any(y in ci for y in r["право"])]
    PA, logA = G.train_bag(BA, len(classes), [(T.features(t, BA), ci[y]) for t, y in trA], [(T.features(t, BA), ci[y]) for t, y in dvA],
                           dict(CFG_A["обучение_ответа"], seed=1), log_prefix="право/знание4")
    obj = {"A": PA, "classes": classes, "cfg": CFG_A, "area": "право"}
    dl = [(r["текст"], r["право"]) for r in law(dev) if any(y in ci for y in r["право"])]
    out = os.path.join(V6, "блоки", "право.знание4")
    os.makedirs(out, exist_ok=True)
    w = os.path.join(out, "веса.npz")
    Z.save(PA, obj, w)
    with open(os.path.join(out, "контроль.jsonl"), "w", encoding="utf-8") as f:
        for t, _ in random.Random(1).sample(lex_dv, 60):
            f.write(json.dumps({"запрос": t, "ожидание": {"область": "право"}}, ensure_ascii=False) + "\n")
    ty = Types(os.path.join(V6, "типы"))
    ps = {"имя": "право.знание4", "версия": 1, "область": "право", "заявка": False,
          "роль": "знание области «право»: правовая тема призыва; учено на ~5000 живых вопросах трёх пулов (чистая разметка)",
          "вход": {"тип": "общие:Направление", "условие": {"область": "право"}}, "выход": {"тип": "общие:Ответ"},
          "архитектура": "знание", "ответы": classes, "настройки": CFG_A,
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": int(sum(v.size for v in PA.values()))},
          "типы": {"общие:Направление": ty.fingerprint("общие:Направление"), "общие:Ответ": ty.fingerprint("общие:Ответ")},
          "контроль": {"файл": "контроль.jsonl"},
          "обучение": dict(info, скрипт="обучение/обучить_пул3.py", когда=datetime.datetime.now().isoformat(timespec="seconds"),
                           строк=len(trA), dev=logA["лучший_dev"],
                           dev_живые_тема="%d/%d" % (sum(Z.run(obj, {"текст": t})["id"] in ys for t, ys in dl), len(dl)))}
    json.dump(ps, open(os.path.join(out, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("записан", out, json.dumps(ps["обучение"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
