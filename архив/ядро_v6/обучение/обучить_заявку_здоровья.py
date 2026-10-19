# -*- coding: utf-8 -*-
"""Заявка области «здоровье», версия 2 — обучается отдельно, соседей не касается.
Свои: те же обучающие тексты, что у заявки v4 (lay train + учитель train_t + тексты статей),
  + живые формы вопроса вокруг описаний болезней («у меня X. берут ли в армию?») — 8000 штук,
  + копии с опечатками (пропуск, перестановка, замена, лишняя буква) — 4000 штук.
Чужие: стандарт фона v2 (как у всех заявок). Калибровка — 2 %-квантиль на своём dev (lay dev), как в v4.
Формы вопроса взяты общими, без слов из размеченных наборов. Запуск: python обучение/обучить_заявку_здоровья.py"""
import datetime
import json
import os
import random
import sys

import numpy as np

V5 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V5)
sys.path.insert(0, os.path.join(V5, "архитектуры"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from ядро.схема import Types, sha256_file  # noqa: E402
from обучение import данные  # noqa: E402
import общее as G  # noqa: E402
import текст as T  # noqa: E402

FRAMES = ["у меня {x}. берут ли в армию?", "{x} — возьмут ли в армию?", "берут ли в армию, если {x}?", "если у меня {x}, заберут ли в армию?",
          "диагноз: {x}. годен ли к службе?", "{x}, какая будет категория годности?", "сыну поставили: {x}. возьмут его служить?",
          "{x}. дают ли освобождение от армии?", "годен ли я, если {x}?", "призовут ли меня, у меня {x}", "врач написал {x}, что будет с армией?",
          "{x}. это статья или нет?", "служить с таким можно? {x}", "{x} и армия — совместимы?", "здравствуйте, {x}. в армию заберут?"]
ALPHA = "абвгдежзийклмнопрстуфхцчшщъыьэюя"
PRE = ["помогите", "всем привет", "здравствуйте", "подскажите пожалуйста", "кто знает", "вопрос такой", "ребят", "срочно", "слушайте", "люди добрые"]
POST = ["что делать", "кто знает", "как быть", "помогите", "подскажите", "заранее спасибо", "не знаю что делать", "очень надо", "пожалуйста ответьте"]


def chatter(t, rnd):
    """Разговорная обёртка: приставка и/или окончание, иногда слово капсом (версия 3)."""
    t = t.rstrip(".?!")
    r = rnd.random()
    if r < 0.4:
        t = rnd.choice(PRE) + " " + t
    elif r < 0.8:
        t = t + " " + rnd.choice(POST)
    else:
        t = rnd.choice(PRE) + " " + t + " " + rnd.choice(POST)
    if rnd.random() < 0.3:
        w = t.split()
        i = rnd.randrange(len(w))
        w[i] = w[i].upper()
        t = " ".join(w)
    return t
CFG = {"корзины_заявки": 1 << 15, "обучение_заявки": {"dim": 16, "lr": 0.005, "batch": 64, "epochs": 20, "patience": 3}}


def typo(t, rnd):
    w = list(t.lower())
    for _ in range(rnd.randint(1, 3)):
        if len(w) < 4:
            break
        i, op = rnd.randrange(1, len(w) - 1), rnd.randrange(4)
        if op == 0:
            del w[i]
        elif op == 1:
            w[i], w[i + 1] = w[i + 1], w[i]
        elif op == 2:
            w[i] = rnd.choice(ALPHA)
        else:
            w.insert(i, rnd.choice(ALPHA))
    s = "".join(w)
    return s.replace(",", "") if rnd.random() < 0.5 else s


def main():
    rnd = random.Random(1)
    base = [t for t, _ in данные.domain_data("здоровье", "train")]
    short = [t.lower().rstrip(".") for t in base if len(t) < 80]
    framed = [rnd.choice(FRAMES).format(x=rnd.choice(short)) for _ in range(8000)]
    noisy = [typo(rnd.choice(base + framed), rnd) for _ in range(4000)]
    version = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    chat = [chatter(rnd.choice(base + framed + noisy), rnd) for _ in range(6000)] if version >= 3 else []
    pos_tr = base + framed + noisy + chat
    dv = [t for t, _ in данные.domain_data("здоровье", "dev")]
    B = CFG["корзины_заявки"]
    ztr = [(T.features(t, B), 1) for t in pos_tr] + [(T.features(t, B), 0) for t in данные.background("train", 2)]
    zdv = [(T.features(t, B), 1) for t in dv] + [(T.features(t, B), 0) for t in данные.background("dev", 2)]
    cnt = np.bincount([y for _, y in ztr], minlength=2)
    PZ, log = G.train_bag(B, 2, ztr, zdv, dict(CFG["обучение_заявки"], seed=1), class_weight=(len(ztr) / (2 * cnt)).tolist(), log_prefix="здоровье/заявка2")
    pz = np.array([float(G.forward(PZ, f)[1]) for f, y in zdv if y == 1])
    pb = np.array([float(G.forward(PZ, f)[1]) for f, y in zdv if y == 0])
    tau = float(min(0.99, max(0.01, np.quantile(pz, 0.02))))
    out = os.path.join(V5, "блоки", "здоровье.заявка%d" % version)
    os.makedirs(out, exist_ok=True)
    w = os.path.join(out, "веса.npz")
    G.save_npz(w, PZ)
    ty = Types(os.path.join(V5, "типы"))
    ps = {"имя": "здоровье.заявка%d" % version, "версия": 1, "область": "здоровье", "заявка": True,
          "роль": "знает, какие вопросы — области «здоровье»; обучена и на живых формах вопроса, и на опечатках",
          "вход": {"тип": "общие:Запрос"}, "выход": {"тип": "общие:Направление", "условие": {"область": "здоровье"}},
          "архитектура": "заявка", "настройки": dict(CFG, порог_калибровки=tau),
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": int(sum(v.size for v in PZ.values()))},
          "типы": {"общие:Запрос": ty.fingerprint("общие:Запрос"), "общие:Направление": ty.fingerprint("общие:Направление")},
          "обучение": {"скрипт": "обучение/обучить_заявку_здоровья.py", "когда": datetime.datetime.now().isoformat(timespec="seconds"),
                       "свои": {"исходные": len(base), "формы_вопроса": len(framed), "с_опечатками": len(noisy), "разговорные": len(chat)},
                       "чужие": "стандарт фона v2 (42 000)", "dev": log["лучший_dev"],
                       "калибровка": {"порог": round(tau, 6), "фон_dev_выше_порога": round(float((pb >= tau).mean()), 4)}}}
    json.dump(ps, open(os.path.join(out, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("записан", out, "чисел", ps["веса"]["чисел"], "dev", log["лучший_dev"], ps["обучение"]["калибровка"])


if __name__ == "__main__":
    main()
