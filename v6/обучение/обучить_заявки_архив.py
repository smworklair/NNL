# -*- coding: utf-8 -*-
"""v6, заявки на архиве Ответов Mail.ru (its5Q/otvetmailru, CC0; готовые куски фильтра).
Метки берутся из самого сайта, ручной разметки нет:
  право «своё»     — раздел «Военная служба» (law_army) со словами про призыв/военкомат/отсрочку/учёт и БЕЗ слов про контракт/часть/увольнение;
  здоровье «своё»  — вопросы архива вида «берут/возьмут ли в армию с …», «годен ли с …», «какая категория с …»;
  «чужое» для обеих — вопросы ДРУГИХ разделов (политика, юмор, семья, суд, кредиты…) со словами про армию/повестку/отсрочку,
                      кроме медицинских и юридических разделов (там свои вопросы встречаются — метка была бы шумной).
Право дополнительно получает «чужим» здоровье-вопросы архива, здоровье — право-вопросы архива.
К этому добавляются прежние данные заявок (как в v6/v5). Выброшены: вопросы наборов свежие2/свежие3/пул2 (по qid) и почти-повторы
всех проверочных наборов (calm_topic, clean_seeds, общий тест, зашумлённые, свежие, свежие2, свежие3, фразы).
Запуск: python обучение/обучить_заявки_архив.py → блоки/право.заявка3, блоки/здоровье.заявка4"""
import datetime
import importlib.util
import json
import os
import random
import re
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
from обучение.обучить_право import unthrottle, live  # noqa: E402
import общее as G  # noqa: E402
import текст as T  # noqa: E402

ARC = r"C:\ЯДРО-ОПЫТ\данные\otvetmailru"
SETS = os.path.join(V6, "реальные", "архив")
LAW = re.compile(r"военкомат|призыв|призов|повестк|отсрочк|военн\w* билет|военник|приписн|воинск\w* уч|медкомисс|комисси|уклон|"
                 r"годност|категори|заберут|забрать|забирают|возьмут|берут", re.I)
SERV = re.compile(r"контракт|военнослужащ|в\s*/\s*ч|воинск\w* част|в част[иь]|увольн|присяг|звани|офицер|прапорщик|сержант|"
                  r"пенси|выслуг|рапорт|комбриг|командир|ипотек|жиль|квартир", re.I)
HEALTH = re.compile(r"(бер[уё]т|возьм[уё]т|призов[уё]т|заберут|годен|годн[аы]|пригоден|категори\w*|отсрочк\w*|освобо\w*)[^.?!]{0,40}"
                    r"\b(с|со|при|если)\b\s+(диагноз|болезн|заболеван|\w+(ом|ем|ой|ей|ью|ами|ями|ием|ением|итом|озом|омой|изм\w*))", re.I)
MED = re.compile(r"диагноз|болезн|болел|заболев|синдром|степен|грыж|остеохондр|плоскостоп|сколиоз|астм|давлен|зрени|миопи|близорук|"
                 r"операци|травм|перелом|кист[аыо]|тахикард|аритм|гастрит|язв|аллерг|псих|невр|эпилеп|сердц|почк|печен|позвоно|сустав|"
                 r"зуб|глаз|слух|недовес|вес\b|рост\b|энурез|заикан|гепатит|вич|туберкул|диабет|щитовид|опухол|анализ|мрт|узи|экг|ээг|"
                 r"врач|лечени|лечил|болит|боли\b|кожн|псориаз|экзем|геморро|варикоз|гайморит|носоглот|ринит|бронхит|лёгк|легк", re.I)
CONSCRIPT = re.compile(r"военкомат|приписн|военн\w* билет|военник|медкомисс|призыв\w*\s+(в\s+арми|комисс|возраст|пункт)|"
                       r"(повестк|отсрочк)\w*[^.?!]{0,30}арми|арми\w*[^.?!]{0,30}(повестк|отсрочк)|заберут|забирают в армию|в армию возьм|берут в армию", re.I)
MED_LAW_CATS = re.compile(r"^(illness|treatment|health|kidhealth|beauty|health_beauty|law.*|edu_high)$")
N_LAW, N_HEALTH, N_NEG = 6000, 4000, 12000
CFG = {"корзины_заявки": 1 << 15, "обучение_заявки": {"dim": 16, "lr": 0.005, "batch": 64, "epochs": 20, "patience": 3}}


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def archive():
    sn = _mod(os.path.join(SETS, "собрать_наборы.py"), "собрать_наборы")
    used = set()
    for n in ("свежие2", "свежие3", "пул2"):
        used |= {r["qid"] for r in json.load(open(os.path.join(SETS, n + "_тексты.json"), encoding="utf-8"))}
    tests = реальные.test_texts()
    for p in (os.path.join(SETS, "разметка_свежие2.jsonl"),):
        tests += [json.loads(l)["вопрос"] for l in open(p, encoding="utf-8")]
    tests += [r["текст"] for r in json.load(open(os.path.join(SETS, "свежие3_тексты.json"), encoding="utf-8"))]
    tests += [json.loads(l)["текст"] for l in open(r"C:\ЯДРО-ОПЫТ\внешние\фразы.jsonl", encoding="utf-8")]
    tests += [json.loads(l)["text"] for l in open(r"C:\Users\Admin\Documents\mailru_style\calm_topic.jsonl", encoding="utf-8")]
    tg = [реальные._grams(t) for t in tests]
    index = {}
    for j, g in enumerate(tg):
        for x in g:
            index.setdefault(x, []).append(j)

    def near(t):
        g = реальные._grams(t)
        hits = {}
        for x in g:
            for j in index.get(x, ()):
                hits[j] = hits.get(j, 0) + 1
        return any(c / len(g | tg[j]) >= 0.5 for j, c in hits.items() if c >= 0.5 * len(g))

    chunks = sorted(os.listdir(os.path.join(ARC, "готово")))
    army, keys = [], []
    for c in chunks:
        army += [json.loads(l) for l in open(os.path.join(ARC, "куски", c, "армия.jsonl"), encoding="utf-8")]
        keys += [json.loads(l) for l in open(os.path.join(ARC, "куски", c, "ключи.jsonl"), encoding="utf-8")]
    rnd = random.Random(11)
    rnd.shuffle(army)
    rnd.shuffle(keys)
    law, health, neg, dropped = [], [], [], 0
    for r in army + keys:
        if r["qid"] in used:
            continue
        t = sn.text(r)
        if len(t) < 12:
            continue
        med = bool(MED.search(t))
        is_h = bool(HEALTH.search(t)) or (med and bool(CONSCRIPT.search(t) or r["кат"] == "law_army")
                                          and not SERV.search(t))
        if r["кат"] == "law_army":
            if is_h:
                if len(health) < N_HEALTH:
                    health.append(t)
            elif LAW.search(t) and not SERV.search(t) and len(law) < N_LAW:
                law.append(t)
            continue
        if is_h:
            if len(health) < N_HEALTH:
                health.append(t)
        elif not MED_LAW_CATS.match(r["кат"]) and not CONSCRIPT.search(t) and len(neg) < N_NEG:
            neg.append(t)
        if len(law) >= N_LAW and len(health) >= N_HEALTH and len(neg) >= N_NEG:
            break
    keep = lambda xs: [t for t in xs if not near(t)]
    n0 = len(law) + len(health) + len(neg)
    law, health, neg = keep(law), keep(health), keep(neg)
    dropped = n0 - len(law) - len(health) - len(neg)
    return {"кусков": chunks, "право": law, "здоровье": health, "чужое": neg, "выброшено_почти_повторов": dropped}


def split(xs, rnd, frac=0.1):
    xs = list(xs)
    rnd.shuffle(xs)
    k = int(len(xs) * frac)
    return xs[k:], xs[:k]


def train_claim(name, area, pos, neg, tau_texts, extra_dev, info):
    B = CFG["корзины_заявки"]
    rnd = random.Random(3)
    ptr, pdv = split(pos, rnd)
    ntr, ndv = split(neg, rnd)
    ztr = [(T.features(t, B), 1) for t in ptr] + [(T.features(t, B), 0) for t in ntr]
    zdv = [(T.features(t, B), 1) for t in pdv] + [(T.features(t, B), 0) for t in ndv]
    cnt = np.bincount([y for _, y in ztr], minlength=2)
    PZ, log = G.train_bag(B, 2, ztr, zdv, dict(CFG["обучение_заявки"], seed=1), class_weight=(len(ztr) / (2 * cnt)).tolist(),
                          log_prefix=name)
    p = lambda t: float(G.forward(PZ, T.features(t, B))[1])
    tau = float(min(0.99, max(0.01, np.quantile([p(t) for t in tau_texts], 0.02))))
    ev = {k: "%d/%d" % (sum(p(t) >= tau for t in xs), len(xs)) for k, xs in extra_dev.items()}
    out = os.path.join(V6, "блоки", name)
    os.makedirs(out, exist_ok=True)
    w = os.path.join(out, "веса.npz")
    G.save_npz(w, PZ)
    ty = Types(os.path.join(V6, "типы"))
    ps = {"имя": name, "версия": 1, "область": area, "заявка": True,
          "роль": "знает, какие вопросы — области «%s»; учена и на вопросах архива Ответов Mail.ru (метки — разделы сайта)" % area,
          "вход": {"тип": "общие:Запрос"}, "выход": {"тип": "общие:Направление", "условие": {"область": area}},
          "архитектура": "заявка", "настройки": dict(CFG, порог_калибровки=tau),
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": int(sum(v.size for v in PZ.values()))},
          "типы": {"общие:Запрос": ty.fingerprint("общие:Запрос"), "общие:Направление": ty.fingerprint("общие:Направление")},
          "обучение": dict(info, скрипт="обучение/обучить_заявки_архив.py", когда=datetime.datetime.now().isoformat(timespec="seconds"),
                           моё=len(ptr), не_моё=len(ntr), dev=log["лучший_dev"], порог=round(tau, 6), выше_порога_на_dev=ev)}
    json.dump(ps, open(os.path.join(out, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("записан", out, json.dumps(ps["обучение"], ensure_ascii=False), flush=True)


def main():
    unthrottle()
    rnd = random.Random(1)
    A = archive()
    print("архив: кусков %d, право %d, здоровье %d, чужое %d, выброшено почти-повторов %d" % (
        len(A["кусков"]), len(A["право"]), len(A["здоровье"]), len(A["чужое"]), A["выброшено_почти_повторов"]), flush=True)
    rows, _ = реальные.pool()
    rnd.shuffle(rows)
    cut = int(len(rows) * 0.15)
    p_dev, p_tr = rows[:cut], rows[cut:]
    bg = данные.background("train", 2)
    info = {"архив_кусков": len(A["кусков"]), "архив_право": len(A["право"]), "архив_здоровье": len(A["здоровье"]),
            "архив_чужое": len(A["чужое"]), "выброшено_почти_повторов": A["выброшено_почти_повторов"]}

    # ---------- право ----------
    lex_tr, lex_dv = данные.domain_data("право", "train"), данные.domain_data("право", "dev")
    pos = [t for t, _ in lex_tr] + [chatter(rnd.choice(lex_tr)[0], rnd) for _ in range(1500)] + [typo(rnd.choice(lex_tr)[0], rnd) for _ in range(1500)]
    for r in p_tr:
        if r["право"] is not None:
            pos += [r["текст"]] * 2 + live(r["текст"], rnd, 6)
    pos += A["право"]
    neg = list(bg)
    for r in p_tr:
        if r["право"] is None:
            neg += [r["текст"]] * 2 + live(r["текст"], rnd, 4)
    neg += A["чужое"] + A["здоровье"]
    train_claim("право.заявка3", "право", pos, neg, [t for t, _ in lex_dv] + [r["текст"] for r in p_dev if r["право"] is not None],
                {"пул_dev_право": [r["текст"] for r in p_dev if r["право"] is not None],
                 "пул_dev_не_право": [r["текст"] for r in p_dev if r["право"] is None],
                 "фон_dev": данные.background("dev", 2)}, info)

    # ---------- здоровье ----------
    base = [t for t, _ in данные.domain_data("здоровье", "train")]
    short = [t.lower().rstrip(".") for t in base if len(t) < 80]
    framed = [rnd.choice(FRAMES).format(x=rnd.choice(short)) for _ in range(8000)]
    noisy = [typo(rnd.choice(base + framed), rnd) for _ in range(4000)]
    chat = [chatter(rnd.choice(base + framed + noisy), rnd) for _ in range(6000)]
    pos = base + framed + noisy + chat
    for r in p_tr:
        if r["здоровье"] is not None:
            pos += [r["текст"]] * 2 + live(r["текст"], rnd, 6)
    pos += A["здоровье"]
    neg = list(bg)
    for r in p_tr:
        if r["здоровье"] is None:
            neg += [r["текст"]] + live(r["текст"], rnd, 2)
    neg += A["чужое"] + A["право"]
    dv = [t for t, _ in данные.domain_data("здоровье", "dev")]
    train_claim("здоровье.заявка4", "здоровье", pos, neg, dv,
                {"пул_dev_здоровье": [r["текст"] for r in p_dev if r["здоровье"] is not None],
                 "пул_dev_не_здоровье": [r["текст"] for r in p_dev if r["здоровье"] is None],
                 "фон_dev": данные.background("dev", 2)}, info)


if __name__ == "__main__":
    main()
