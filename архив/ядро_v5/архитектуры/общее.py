# -*- coding: utf-8 -*-
"""Общий код архитектур (без весов): признаки по хешу, прямой проход на numpy, обучение на torch.

Модели — семья fastText: мешок признаков → среднее векторов → (скрытый слой tanh) → линейный слой → softmax.
Одна и та же функция обучения и одни и те же настройки у блоков и у монолита (разница — только данные, признаки, классы).
"""
import importlib.util
import os
import time
import zlib

import numpy as np

DEFAULTS = {"dim": 64, "hidden": 0, "lr": 0.005, "batch": 32, "epochs": 30, "patience": 4, "seed": 1}


def h(s, buckets):
    return zlib.crc32(s.encode("utf-8")) % buckets


def char_ngrams(word, lo, hi):
    w = "<" + word + ">"
    return [w[i:i + n] for n in range(lo, hi + 1) for i in range(len(w) - n + 1)]


def load_canon(types_dir):
    spec = importlib.util.spec_from_file_location("canon_v3", os.path.join(types_dir, "канон.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_vocab(types_dir):
    with open(os.path.join(types_dir, "словарь.txt"), encoding="utf-8") as f:
        vocab = [l.rstrip("\n") for l in f if l.strip()]
    return vocab, {s: i for i, s in enumerate(vocab)}


# ---------------- numpy: прямой проход ----------------
def softmax(z):
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def forward(P, idx):
    """P: emb, (W1, b1), W, b. idx — список индексов признаков. Возвращает вероятности классов."""
    emb = P["emb"]
    x = emb[np.asarray(idx, dtype=np.int64)].mean(0) if len(idx) else np.zeros(emb.shape[1], dtype=emb.dtype)
    if "W1" in P:
        x = np.tanh(x @ P["W1"] + P["b1"])
    return softmax((x @ P["W"] + P["b"]).astype(np.float64))


def top(probs, classes, k=5):
    order = np.argsort(-probs, kind="stable")[:k]
    return [[classes[i], float(probs[i])] for i in order]


# ---------------- сохранение ----------------
def save_npz(path, arrays):
    with open(path, "wb") as f:
        np.savez(f, **arrays)


def load_npz(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


# ---------------- torch: обучение ----------------
def train_bag(n_feat, n_cls, train, dev, cfg=None, init=None, class_weight=None, log_prefix=""):
    """train/dev: [(список индексов признаков, номер класса)]. Ранняя остановка по точности на dev.
    init — словарь numpy-массивов для дообучения (иначе с нуля). Возвращает (параметры numpy, журнал)."""
    import torch
    import torch.nn as nn

    c = dict(DEFAULTS)
    c.update(cfg or {})
    torch.manual_seed(c["seed"])
    rng = np.random.RandomState(c["seed"])

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.emb = nn.EmbeddingBag(n_feat, c["dim"], mode="mean")
            nn.init.uniform_(self.emb.weight, -0.1, 0.1)
            d = c["dim"]
            if c["hidden"]:
                self.l1 = nn.Linear(d, c["hidden"])
                d = c["hidden"]
            self.out = nn.Linear(d, n_cls)

        def forward(self, flat, offsets):
            x = self.emb(flat, offsets)
            if c["hidden"]:
                x = torch.tanh(self.l1(x))
            return self.out(x)

    net = Net()
    if init is not None:
        with torch.no_grad():
            net.emb.weight.copy_(torch.from_numpy(init["emb"]))
            if c["hidden"]:
                net.l1.weight.copy_(torch.from_numpy(init["W1"].T))
                net.l1.bias.copy_(torch.from_numpy(init["b1"]))
            net.out.weight.copy_(torch.from_numpy(init["W"].T))
            net.out.bias.copy_(torch.from_numpy(init["b"]))
    opt = torch.optim.Adam(net.parameters(), lr=c["lr"])
    wt = torch.tensor(class_weight, dtype=torch.float32) if class_weight is not None else None
    lossf = nn.CrossEntropyLoss(weight=wt)

    def batch(rows):
        flat, offs, y = [], [], []
        for idx, lab in rows:
            offs.append(len(flat))
            flat.extend(idx)
            y.append(lab)
        return torch.tensor(flat, dtype=torch.long), torch.tensor(offs, dtype=torch.long), torch.tensor(y, dtype=torch.long)

    def evaluate(rows):
        if not rows:
            return 0.0
        net.eval()
        ok = 0
        with torch.no_grad():
            for i in range(0, len(rows), 512):
                f, o, y = batch(rows[i:i + 512])
                ok += int((net(f, o).argmax(1) == y).sum())
        net.train()
        return ok / len(rows)

    def export():
        P = {"emb": net.emb.weight.detach().numpy().astype(np.float32).copy(),
             "W": net.out.weight.detach().numpy().T.astype(np.float32).copy(),
             "b": net.out.bias.detach().numpy().astype(np.float32).copy()}
        if c["hidden"]:
            P["W1"] = net.l1.weight.detach().numpy().T.astype(np.float32).copy()
            P["b1"] = net.l1.bias.detach().numpy().astype(np.float32).copy()
        return P

    t0 = time.time()
    best, best_acc, bad, log = export(), evaluate(dev), 0, []
    for ep in range(c["epochs"]):
        order = rng.permutation(len(train))
        tot = 0.0
        for i in range(0, len(order), c["batch"]):
            f, o, y = batch([train[j] for j in order[i:i + c["batch"]]])
            opt.zero_grad()
            loss = lossf(net(f, o), y)
            loss.backward()
            opt.step()
            tot += float(loss.detach()) * len(y)
        acc = evaluate(dev)
        log.append({"эпоха": ep + 1, "loss": round(tot / len(train), 4), "dev": round(acc, 4)})
        print("%s эпоха %d loss %.4f dev %.4f" % (log_prefix, ep + 1, tot / len(train), acc), flush=True)
        if acc > best_acc or ep == 0 and not dev:
            best, best_acc, bad = export(), acc, 0
        else:
            bad += 1
            if dev and bad >= c["patience"]:
                break
    if not dev:
        best = export()
    return best, {"эпох": len(log), "лучший_dev": round(best_acc, 4), "время_с": round(time.time() - t0, 1), "ход": log}
