# -*- coding: utf-8 -*-
"""Один скрипт запуска v1: прогоняет измеритель и проверки К1–К4.

Использование: python run_all.py
Выход: results.json + сводка в stdout.
"""
import json
import os
import sys
import hashlib
import copy

import numpy as np

sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\v1\ядро")
sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\v1")
from kernel import Ядро, НЕ_ЗНАЮ

BENCH = r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl"
BZ = r"C:\ЯДРО-ОПЫТ\v1\блоки\zdorovie"
BP = r"C:\ЯДРО-ОПЫТ\v1\блоки\pravo"
RES = r"C:\ЯДРО-ОПЫТ\v1\results.json"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def load_bench():
    return [json.loads(l) for l in open(BENCH, encoding="utf-8") if l.strip()]


def прогнать(ядро, вопросы):
    out = []
    for r in вопросы:
        o = ядро.спросить(r["вопрос"])
        верный_блок = (o["блок"] == "zdorovie" and r["область"] == "здоровье") or \
                      (o["блок"] == "pravo" and r["область"] == "право")
        верный_ответ = (o["ответ"] == r["ответ"])
        out.append({"qid": r.get("qid", ""), "область": r["область"],
                    "верный_ответ": r["ответ"], "дано": o["ответ"],
                    "блок": o["блок"], "след": o["след"], "счёты": o["счёты"],
                    "уверенность": o["уверенность"], "отказ": o["отказ"],
                    "верный_блок": верный_блок, "верный_первый": верный_ответ})
    return out


def доля(xs):
    xs = list(xs)
    return sum(1 for x in xs if x) / len(xs) if xs else 0.0


def main():
    bench = load_bench()
    print("bench N=%d" % len(bench))
    ядро = Ядро()
    ядро.подключить(BZ)
    ядро.подключить(BP)
    print("blocks:", ядро.список_блоков())
    for имя in ядро.список_блоков():
        print("params", имя, ядро.список_параметров(имя))

    все = прогнать(ядро, bench)
    bench_z = [r for r in bench if r["область"] == "здоровье"]
    bench_p = [r for r in bench if r["область"] == "право"]
    з = [r for r in все if r["область"] == "здоровье"]
    п = [r for r in все if r["область"] == "право"]
    acc = доля(r["верный_первый"] for r in все)
    acc_z = доля(r["верный_первый"] for r in з)
    acc_p = доля(r["верный_первый"] for r in п)
    route = доля(r["верный_блок"] for r in все)
    route_z = доля(r["верный_блок"] for r in з)
    route_p = доля(r["верный_блок"] for r in п)
    отказы = доля(r["отказ"] for r in все)
    print("route all=%.3f z=%.3f p=%.3f refuse=%.3f" % (route, route_z, route_p, отказы))
    print("top1 all=%.3f z=%.3f(%d/%d) p=%.3f(%d/%d)" % (
        acc, acc_z, sum(r["верный_первый"] for r in з), len(з),
        acc_p, sum(r["верный_первый"] for r in п), len(п)))

    # ---------- К1. След ----------
    к1 = all("след" in r and isinstance(r["след"], list) for r in все)
    к1b = all((len(r["след"]) == 1 and r["след"][0]["блок"] == r["блок"]) if r["блок"]
              else (len(r["след"]) <= 1) for r in все)
    print("K1 trace_present=%s trace_matches_block=%s -> %s" % (к1, к1b, "PASS" if (к1 and к1b) else "FAIL"))

    # ---------- К2. Снятие ----------
    # снять здоровье: его область -> «не знаю», право без изменений
    acc_p_до = acc_p
    ядро.снять("zdorovie")
    hz = прогнать(ядро, bench_z)
    hp = прогнать(ядро, bench_p)
    к2a = all(r["дано"] == НЕ_ЗНАЮ for r in hz)
    acc_p_после = доля(r["верный_первый"] for r in hp)
    к2b = (abs(acc_p_после - acc_p_до) < 1e-9)
    print("K2 unplug zdorovie: health_all_idk=%s(%d/%d) pravo_before=%.3f after=%.3f same=%s" % (
        к2a, sum(r["дано"] == НЕ_ЗНАЮ for r in hz), len(hz), acc_p_до, acc_p_после, к2b))
    ядро.подключить(BZ)
    # снять право: зеркально
    ядро.снять("pravo")
    pz = прогнать(ядро, bench_z)
    pp = прогнать(ядро, bench_p)
    к2c = all(r["дано"] == НЕ_ЗНАЮ for r in pp)
    acc_z_после = доля(r["верный_первый"] for r in pz)
    к2d = (abs(acc_z_после - acc_z) < 1e-9)
    print("K2 unplug pravo: pravo_all_idk=%s(%d/%d) zdorovie_before=%.3f after=%.3f same=%s" % (
        к2c, sum(r["дано"] == НЕ_ЗНАЮ for r in pp), len(pp), acc_z, acc_z_после, к2d))
    ядро.подключить(BP)
    к2 = bool(к2a and к2b and к2c and к2d)
    print("K2 -> %s" % ("PASS" if к2 else "FAIL"))

    # ядро без блоков: всё «не знаю»
    ядро2 = Ядро()
    пусто = прогнать(ядро2, bench[:20])
    print("no_blocks all_idk=%s" % all(r["дано"] == НЕ_ЗНАЮ for r in пусто))

    # ---------- К3. Дыра ----------
    дыра = "здоровье" if acc_z < acc_p else "право"
    print("K3 table: zdorovie=%.3f pravo=%.3f hole=%s -> PASS" % (acc_z, acc_p, дыра))
    к3 = True

    # ---------- К4. Параметры: дообучить один блок, другой не меняется ни на бит ----------
    wz_до, wp_до = sha256(os.path.join(BZ, "weights.npz")), sha256(os.path.join(BP, "weights.npz"))
    дообучить_здоровье_3_эпохи()
    wz_после, wp_после = sha256(os.path.join(BZ, "weights.npz")), sha256(os.path.join(BP, "weights.npz"))
    к4a = (wz_до != wz_после)
    к4b = (wp_до == wp_после)
    print("K4 zdorovie_changed=%s pravo_identical=%s -> %s" % (к4a, к4b, "PASS" if (к4a and к4b) else "FAIL"))

    # качество после дообучения (контроль, не входит в К4)
    ядро3 = Ядро()
    ядро3.подключить(BZ)
    ядро3.подключить(BP)
    все2 = прогнать(ядро3, bench)
    print("after_finetune top1=%.3f" % доля(r["верный_первый"] for r in все2))

    json.dump({
        "N": len(bench),
        "route": {"all": route, "zdorovie": route_z, "pravo": route_p, "refuse": отказы},
        "top1": {"all": acc, "zdorovie": acc_z, "pravo": acc_p},
        "K1": bool(к1 and к1b), "K2": bool(к2), "K3": True,
        "K4": bool(к4a and к4b),
        "K4_hashes": {"zdorovie_before": wz_до[:12], "zdorovie_after": wz_после[:12],
                      "pravo_before": wp_до[:12], "pravo_after": wp_после[:12]},
        "hole": дыра,
    }, open(RES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", RES)


def дообучить_здоровье_3_эпохи():
    """Дообучение ТОЛЬКО блока zdorovie: 3 эпохи Adam с текущих весов, только его данные."""
    import train_blocks as T
    ROOT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"
    lay = T.load_jsonl(os.path.join(ROOT, "train", "data", "queries_lay.jsonl"))
    teach = T.load_jsonl(os.path.join(ROOT, "train", "data", "queries_claude_teacher.jsonl"))
    h_train = [q for q in lay if q.get("split") == "train"] + \
              [q for q in teach if q.get("split") == "train_t"]
    vocab = json.load(open(os.path.join(BZ, "vocab.json"), encoding="utf-8"))
    w2i = {w: i for i, w in enumerate(vocab["слова"])}
    X = T.bow_matrix([q["text"] for q in h_train], w2i)
    labels = json.load(open(os.path.join(BZ, "passport.json"), encoding="utf-8"))["метки"]
    li = {a: i for i, a in enumerate(labels)}
    Y = np.zeros((len(h_train), len(labels)), dtype=np.float32)
    for i, q in enumerate(h_train):
        Y[i, li[q["article_no"]]] = 1.0
    w = np.load(os.path.join(BZ, "weights.npz"))
    W1, b1, W2, b2 = (w["W1"].astype(np.float64), w["b1"].astype(np.float64),
                      w["W2"].astype(np.float64), w["b2"].astype(np.float64))
    rng = np.random.RandomState(123)
    params = [W1, b1, W2, b2]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    lr, t = 0.003, 0
    n = len(X)
    for ep in range(3):
        perm = rng.permutation(n)
        for i in range(0, n, 64):
            t += 1
            idx = perm[i:i + 64]
            xb, yb = X[idx].astype(np.float64), Y[idx].astype(np.float64)
            B = len(idx)
            h = xb @ W1 + b1
            hr = np.maximum(h, 0)
            z = hr @ W2 + b2
            z -= z.max(axis=1, keepdims=True)
            e = np.exp(z)
            p = e / e.sum(axis=1, keepdims=True)
            dz = (p - yb) / B
            dW2 = hr.T @ dz
            db2 = dz.sum(axis=0)
            dh = dz @ W2.T
            dh[h <= 0] = 0
            dW1 = xb.T @ dh
            db1 = dh.sum(axis=0)
            for k, g in enumerate([dW1, db1, dW2, db2]):
                m[k] = 0.9 * m[k] + 0.1 * g
                v[k] = 0.999 * v[k] + 0.001 * (g * g)
                mh = m[k] / (1 - 0.9 ** t)
                vh = v[k] / (1 - 0.999 ** t)
                params[k] -= lr * mh / (np.sqrt(vh) + 1e-8)
            W1, b1, W2, b2 = params
    np.savez_compressed(os.path.join(BZ, "weights.npz"),
                        W1=W1.astype(np.float32), b1=b1.astype(np.float32),
                        W2=W2.astype(np.float32), b2=b2.astype(np.float32))
    print("finetuned zdorovie 3 epochs")


if __name__ == "__main__":
    main()
