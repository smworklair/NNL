# -*- coding: utf-8 -*-
"""v6: заявки права и здоровья + знание права на чистой разметке живых вопросов.
Пул 1 — 1180 вопросов calm_topic (разметка Claude, реальные/пул_метки.py); пул 2 — 1000 вопросов архива Ответов Mail.ru
(разметка Muse Spark, C:\\ЯДРО-ОПЫТ\\внешние\\разметка_пул2.jsonl; сверка Muse Spark с Claude на свежие2 — 189/200).
Спорные не идут. Почти-повторы любых проверочных наборов (вкл. свежие2, свежие3, фразы) выброшены. 15 % пулов — dev.
Один вариант, без подбора. Запуск: python обучение/обучить_чистое.py → блоки/право.заявка4, право.знание3, здоровье.заявка5"""
import datetime
import json
import os
import random
import sys

V6 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V6)
sys.path.insert(0, os.path.join(V6, "архитектуры"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from ядро.схема import Types, sha256_file  # noqa: E402
from обучение import данные, реальные  # noqa: E402
from обучение.обучить_заявку_здоровья import FRAMES, chatter, typo  # noqa: E402
from обучение.обучить_право import CFG_A, live, unthrottle  # noqa: E402
from обучение.обучить_заявки_архив import train_claim  # noqa: E402
import общее as G  # noqa: E402
import текст as T  # noqa: E402
import знание as Z  # noqa: E402

EXT = r"C:\ЯДРО-ОПЫТ\внешние"
SETS = os.path.join(V6, "реальные", "архив")


def pool2():
    texts = json.load(open(os.path.join(SETS, "пул2_тексты.json"), encoding="utf-8"))
    tests = реальные.test_texts()
    tests += [json.loads(l)["вопрос"] for l in open(os.path.join(SETS, "разметка_свежие2.jsonl"), encoding="utf-8")]
    tests += [r["текст"] for r in json.load(open(os.path.join(SETS, "свежие3_тексты.json"), encoding="utf-8"))]
    tests += [json.loads(l)["текст"] for l in open(os.path.join(EXT, "фразы.jsonl"), encoding="utf-8")]
    tg = [реальные._grams(t) for t in tests]
    rows, dropped = [], 0
    for l in open(os.path.join(EXT, "разметка_пул2.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        if r["область"] == "спорно":
            continue
        t = texts[r["i"]]["текст"]
        g = реальные._grams(t)
        if any(len(g & h) / len(g | h) >= 0.5 for h in tg):
            dropped += 1
            continue
        rows.append({"текст": t, "право": r["ответы"] if r["область"] == "право" else None,
                     "здоровье": r["ответы"] if r["область"] == "здоровье" else None})
    return rows, dropped


def main():
    unthrottle()
    rnd = random.Random(1)
    p1, _ = реальные.pool()
    p2, dropped2 = pool2()
    rows = p1 + p2
    rnd.shuffle(rows)
    cut = int(len(rows) * 0.15)
    dev, tr = rows[:cut], rows[cut:]
    law = lambda rs: [r for r in rs if r["право"] is not None]
    nolaw = lambda rs: [r for r in rs if r["право"] is None]
    hl = lambda rs: [r for r in rs if r["здоровье"] is not None]
    nohl = lambda rs: [r for r in rs if r["здоровье"] is None]
    info = {"пул1": len(p1), "пул2": len(p2), "пул2_выброшено_почти_повторов": dropped2, "dev": len(dev),
            "право_живых": len(law(tr)), "здоровье_живых": len(hl(tr))}
    print(info, flush=True)
    bg = данные.background("train", 2)
    lex_tr, lex_dv = данные.domain_data("право", "train"), данные.domain_data("право", "dev")

    # ---------- заявка права ----------
    pos = [t for t, _ in lex_tr] + [chatter(rnd.choice(lex_tr)[0], rnd) for _ in range(1500)] + [typo(rnd.choice(lex_tr)[0], rnd) for _ in range(1500)]
    for r in law(tr):
        pos += [r["текст"]] * 2 + live(r["текст"], rnd, 6)
    neg = list(bg)
    for r in nolaw(tr):
        neg += [r["текст"]] * 2 + live(r["текст"], rnd, 4)
    train_claim("право.заявка4", "право", pos, neg, [t for t, _ in lex_dv] + [r["текст"] for r in law(dev)],
                {"dev_право": [r["текст"] for r in law(dev)], "dev_не_право": [r["текст"] for r in nolaw(dev)],
                 "фон_dev": данные.background("dev", 2)}, dict(info, данные="пул1+пул2 (чистая разметка)"))

    # ---------- заявка здоровья ----------
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
    train_claim("здоровье.заявка5", "здоровье", pos, neg, [t for t, _ in данные.domain_data("здоровье", "dev")],
                {"dev_здоровье": [r["текст"] for r in hl(dev)], "dev_не_здоровье": [r["текст"] for r in nohl(dev)],
                 "фон_dev": данные.background("dev", 2)}, dict(info, данные="пул1+пул2 (чистая разметка)"))

    # ---------- знание права: только темы ----------
    classes = данные.classes("право")
    ci = {c: i for i, c in enumerate(classes)}
    BA = CFG_A["корзины_ответа"]
    trA = list(lex_tr)
    for r in law(tr):
        for y in r["право"]:
            trA += [(r["текст"], y)] * 2 + [(x, y) for x in live(r["текст"], rnd, 4)]
    dvA = list(lex_dv) + [(r["текст"], r["право"][0]) for r in law(dev) if r["право"]]
    PA, logA = G.train_bag(BA, len(classes), [(T.features(t, BA), ci[y]) for t, y in trA], [(T.features(t, BA), ci[y]) for t, y in dvA],
                           dict(CFG_A["обучение_ответа"], seed=1), log_prefix="право/знание3")
    obj = {"A": PA, "classes": classes, "cfg": CFG_A, "area": "право"}
    dl = [(r["текст"], r["право"]) for r in law(dev) if r["право"]]
    out = os.path.join(V6, "блоки", "право.знание3")
    os.makedirs(out, exist_ok=True)
    w = os.path.join(out, "веса.npz")
    Z.save(PA, obj, w)
    with open(os.path.join(out, "контроль.jsonl"), "w", encoding="utf-8") as f:
        for t, _ in random.Random(1).sample(lex_dv, 60):
            f.write(json.dumps({"запрос": t, "ожидание": {"область": "право"}}, ensure_ascii=False) + "\n")
    ty = Types(os.path.join(V6, "типы"))
    ps = {"имя": "право.знание3", "версия": 1, "область": "право", "заявка": False,
          "роль": "знание области «право»: правовая тема призыва; учено и на живых вопросах двух пулов (чистая разметка)",
          "вход": {"тип": "общие:Направление", "условие": {"область": "право"}}, "выход": {"тип": "общие:Ответ"},
          "архитектура": "знание", "ответы": classes, "настройки": CFG_A,
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": int(sum(v.size for v in PA.values()))},
          "типы": {"общие:Направление": ty.fingerprint("общие:Направление"), "общие:Ответ": ty.fingerprint("общие:Ответ")},
          "контроль": {"файл": "контроль.jsonl"},
          "обучение": dict(info, скрипт="обучение/обучить_чистое.py", когда=datetime.datetime.now().isoformat(timespec="seconds"),
                           строк=len(trA), dev=logA["лучший_dev"],
                           dev_живые_тема="%d/%d" % (sum(Z.run(obj, {"текст": t})["id"] in ys for t, ys in dl), len(dl)))}
    json.dump(ps, open(os.path.join(out, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("записан", out, json.dumps(ps["обучение"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
