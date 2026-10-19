# -*- coding: utf-8 -*-
"""v6: заявка и знание области «право» нового образца — обучаются отдельно, данные других блоков не читаются.
Свои данные: вопросы учителя (lex train + тексты тем), настоящие вопросы пула (Ответы Mail.ru, размечены учителем) и их
живые копии (опечатки, разговорные обёртки). «Не моё»: стандарт фона v2 + вопросы пула, которые учитель пометил «не право»
(вне темы и чистое здоровье). Знание получает класс «∅» — «ничего не подходит» (вопросы «не право»).
15 % пула (по зерну) — dev для остановки; проверочные наборы не читаются (почти-повторы выброшены в обучение/реальные.py).
Запуск: python обучение/обучить_право.py"""
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
from обучение.обучить_заявку_здоровья import chatter, typo  # noqa: E402
import общее as G  # noqa: E402
import текст as T  # noqa: E402
import знание as Z  # noqa: E402

CFG_Z = {"корзины_заявки": 1 << 15, "обучение_заявки": {"dim": 16, "lr": 0.005, "batch": 64, "epochs": 20, "patience": 3}}
CFG_A = {"корзины_ответа": 1 << 16, "обучение_ответа": {"dim": 24, "lr": 0.005, "batch": 32, "epochs": 30, "patience": 4}}


def unthrottle():
    try:
        import ctypes

        class S(ctypes.Structure):
            _fields_ = [("Version", ctypes.c_ulong), ("ControlMask", ctypes.c_ulong), ("StateMask", ctypes.c_ulong)]
        k = ctypes.windll.kernel32
        s = S(1, 1, 0)
        k.SetProcessInformation(k.GetCurrentProcess(), 4, ctypes.byref(s), ctypes.sizeof(s))
    except Exception:
        pass


def live(t, rnd, n):
    """n живых копий настоящего вопроса: опечатки и разговорные обёртки."""
    return [typo(t, rnd) if k % 2 == 0 else chatter(t, rnd) for k in range(n)]


def main(n_fon=3000, real_live=2, only_knowledge=False, suffix=""):
    unthrottle()
    rnd = random.Random(1)
    rows, dropped = реальные.pool()
    rnd.shuffle(rows)
    cut = int(len(rows) * 0.15)
    p_dev, p_tr = rows[:cut], rows[cut:]
    law = lambda rs: [r for r in rs if r["право"] is not None]
    other = lambda rs: [r for r in rs if r["право"] is None]
    classes = данные.classes("право") + [Z.NOTHING]
    ci = {c: i for i, c in enumerate(classes)}
    lex_tr, lex_dv = данные.domain_data("право", "train"), данные.domain_data("право", "dev")
    ty = Types(os.path.join(V6, "типы"))
    when = datetime.datetime.now().isoformat(timespec="seconds")

    # ---------- заявка: моё / не моё ----------
    if only_knowledge:
        return knowledge(rnd, p_tr, p_dev, law, other, classes, ci, lex_tr, lex_dv, ty, when, n_fon, real_live, suffix)
    pos = [t for t, _ in lex_tr] + [chatter(rnd.choice(lex_tr)[0], rnd) for _ in range(1500)] + [typo(rnd.choice(lex_tr)[0], rnd) for _ in range(1500)]
    for r in law(p_tr):
        pos += [r["текст"]] * 2 + live(r["текст"], rnd, 6)
    neg_real = []
    for r in other(p_tr):
        neg_real += [r["текст"]] * 2 + live(r["текст"], rnd, 4)
    neg = данные.background("train", 2) + neg_real
    BZ = CFG_Z["корзины_заявки"]
    ztr = [(T.features(t, BZ), 1) for t in pos] + [(T.features(t, BZ), 0) for t in neg]
    dv_pos = [t for t, _ in lex_dv] + [r["текст"] for r in law(p_dev)]
    dv_neg = данные.background("dev", 2) + [r["текст"] for r in other(p_dev)]
    zdv = [(T.features(t, BZ), 1) for t in dv_pos] + [(T.features(t, BZ), 0) for t in dv_neg]
    cnt = np.bincount([y for _, y in ztr], minlength=2)
    PZ, logZ = G.train_bag(BZ, 2, ztr, zdv, dict(CFG_Z["обучение_заявки"], seed=1), class_weight=(len(ztr) / (2 * cnt)).tolist(), log_prefix="право/заявка2")
    pz = np.array([float(G.forward(PZ, T.features(t, BZ))[1]) for t in [t for t, _ in lex_dv]])
    tau = float(min(0.99, max(0.01, np.quantile(pz, 0.02))))
    pr = np.array([float(G.forward(PZ, T.features(r["текст"], BZ))[1]) for r in other(p_dev)])
    pl = np.array([float(G.forward(PZ, T.features(r["текст"], BZ))[1]) for r in law(p_dev)])
    pb = np.array([float(G.forward(PZ, T.features(t, BZ))[1]) for t in данные.background("dev", 2)])
    out = os.path.join(V6, "блоки", "право.заявка2")
    os.makedirs(out, exist_ok=True)
    w = os.path.join(out, "веса.npz")
    G.save_npz(w, PZ)
    ps = {"имя": "право.заявка2", "версия": 1, "область": "право", "заявка": True,
          "роль": "знает, какие вопросы — правовые вопросы призыва; учена и на настоящих вопросах людей, и на том, что «не право»",
          "вход": {"тип": "общие:Запрос"}, "выход": {"тип": "общие:Направление", "условие": {"область": "право"}},
          "архитектура": "заявка", "настройки": dict(CFG_Z, порог_калибровки=tau),
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": int(sum(v.size for v in PZ.values()))},
          "типы": {"общие:Запрос": ty.fingerprint("общие:Запрос"), "общие:Направление": ty.fingerprint("общие:Направление")},
          "обучение": {"скрипт": "обучение/обучить_право.py", "когда": when, "моё": len(pos), "не_моё": len(neg),
                       "из_них_настоящих_не_моё": len(neg_real), "dev": logZ["лучший_dev"],
                       "калибровка": {"порог": round(tau, 6), "фон_dev_выше": round(float((pb >= tau).mean()), 4),
                                      "пул_dev_не_право_выше": "%d/%d" % (int((pr >= tau).sum()), len(pr)),
                                      "пул_dev_право_выше": "%d/%d" % (int((pl >= tau).sum()), len(pl))}}}
    json.dump(ps, open(os.path.join(out, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("записан", out, json.dumps(ps["обучение"], ensure_ascii=False), flush=True)

    return knowledge(rnd, p_tr, p_dev, law, other, classes, ci, lex_tr, lex_dv, ty, when, n_fon, real_live, suffix)


def knowledge(rnd, p_tr, p_dev, law, other, classes, ci, lex_tr, lex_dv, ty, when, n_fon, real_live, suffix):
    # ---------- знание: тема или «∅» ----------
    BA = CFG_A["корзины_ответа"]
    tr = [(t, y) for t, y in lex_tr]
    for r in law(p_tr):
        for y in r["право"]:
            tr += [(r["текст"], y)] * 2 + [(x, y) for x in live(r["текст"], rnd, 4)]
    nothing = []
    for r in other(p_tr):
        nothing += [r["текст"]] + live(r["текст"], rnd, real_live)
    nothing += rnd.sample(данные.background("train", 2), n_fon)
    tr += [(t, Z.NOTHING) for t in nothing]
    dv = [(t, y) for t, y in lex_dv] + [(r["текст"], r["право"][0]) for r in law(p_dev) if r["право"]] + [(r["текст"], Z.NOTHING) for r in other(p_dev)]
    PA, logA = G.train_bag(BA, len(classes), [(T.features(t, BA), ci[y]) for t, y in tr], [(T.features(t, BA), ci[y]) for t, y in dv],
                           dict(CFG_A["обучение_ответа"], seed=1), log_prefix="право/знание2")
    obj = {"A": PA, "classes": classes, "cfg": CFG_A, "area": "право"}
    acc = lambda rs: sum(Z.run(obj, {"текст": t})["id"] == y and Z.run(obj, {"текст": t})["p"] > 0 for t, y in rs) / max(1, len(rs))
    pdl = [(r["текст"], r["право"]) for r in law(p_dev) if r["право"]]
    out = os.path.join(V6, "блоки", "право.знание2" + suffix)
    os.makedirs(out, exist_ok=True)
    w = os.path.join(out, "веса.npz")
    Z.save(PA, obj, w)
    rows_ctrl = rnd.sample(lex_dv, 60)
    with open(os.path.join(out, "контроль.jsonl"), "w", encoding="utf-8") as f:
        for t, _ in rows_ctrl:
            f.write(json.dumps({"запрос": t, "ожидание": {"область": "право"}}, ensure_ascii=False) + "\n")
    ps = {"имя": "право.знание2" + suffix, "версия": 1, "область": "право", "заявка": False,
          "роль": "знание области «право»: правовая тема призыва по вопросу человека; своё «∅ — ничего не подходит»",
          "вход": {"тип": "общие:Направление", "условие": {"область": "право"}}, "выход": {"тип": "общие:Ответ"},
          "архитектура": "знание", "ответы": classes, "настройки": CFG_A, "порог_ответа": 1e-6,
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": int(sum(v.size for v in PA.values()))},
          "типы": {"общие:Направление": ty.fingerprint("общие:Направление"), "общие:Ответ": ty.fingerprint("общие:Ответ")},
          "контроль": {"файл": "контроль.jsonl"},
          "обучение": {"скрипт": "обучение/обучить_право.py", "когда": when, "строк": len(tr), "из_них_ничего": len(nothing),
                       "ничего_фон": n_fon, "ничего_живых_копий": real_live,
                       "настоящих_право": len(law(p_tr)), "dev": logA["лучший_dev"],
                       "пул_dev_тема_верна": "%d/%d" % (sum(Z.run(obj, {"текст": t})["id"] in ys for t, ys in pdl), len(pdl)),
                       "пул_dev_не_право_ничего": "%d/%d" % (sum(Z.run(obj, {"текст": r["текст"]})["p"] == 0 for r in other(p_dev)), len(other(p_dev))),
                       "lex_dev": round(acc(lex_dv), 4)}}
    json.dump(ps, open(os.path.join(out, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("записан", out, json.dumps(ps["обучение"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a:   # подбор баланса «∅» по dev: python обучение/обучить_право.py <фон> <копий> <суффикс>
        main(int(a[0]), int(a[1]), True, a[2])
    else:
        main()
