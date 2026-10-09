# -*- coding: utf-8 -*-
"""Обучение блока-решателя задач с нуля (без чужих весов), отдельно от всех блоков.
Данные: задачи/наборы/train.jsonl (генератор ru+en + GSM8K ru+en), остановка — по потерям на dev.
Трансформер-декодер: куски слов (sentencepiece, обучен на train) → решение по шагам. Потери — только на решении.
Запуск: python обучение/обучить_решатель.py --размер малый|большой [--эпох 5] [--выход блоки_задачи/задачи]"""
import argparse
import datetime
import json
import math
import os
import random
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

V4 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V4)
sys.path.insert(0, os.path.join(V4, "архитектуры"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from ядро.схема import Types, sha256_file  # noqa: E402
import общее as G  # noqa: E402
import решатель as R  # noqa: E402
import решатель2 as R2  # noqa: E402
import числа as C  # noqa: E402

SETS = os.path.join(V4, "задачи", "наборы")
SIZES = {"малый": {"dim": 128, "слоёв": 4, "голов": 4}, "большой": {"dim": 256, "слоёв": 6, "голов": 8}}
CTX = 512


class Block(nn.Module):
    def __init__(self, d, h):
        super().__init__()
        self.h = h
        self.ln1, self.ln2 = nn.LayerNorm(d), nn.LayerNorm(d)
        self.qkv, self.proj = nn.Linear(d, 3 * d), nn.Linear(d, d)
        self.fc, self.out = nn.Linear(d, 4 * d), nn.Linear(4 * d, d)

    def forward(self, x, drop):
        B, T, d = x.shape
        q, k, v = self.qkv(self.ln1(x)).split(d, dim=2)
        q, k, v = (t.view(B, T, self.h, d // self.h).transpose(1, 2) for t in (q, k, v))
        o = F.scaled_dot_product_attention(q, k, v, is_causal=True, dropout_p=drop if self.training else 0.0)
        x = x + F.dropout(self.proj(o.transpose(1, 2).reshape(B, T, d)), drop, self.training)
        h = self.out(F.gelu(self.fc(self.ln2(x)), approximate="tanh"))
        return x + F.dropout(h, drop, self.training)


class GPT(nn.Module):
    def __init__(self, V, d, L, H, drop):
        super().__init__()
        self.tok, self.pos = nn.Embedding(V, d), nn.Embedding(CTX, d)
        self.blocks = nn.ModuleList(Block(d, H) for _ in range(L))
        self.lnf = nn.LayerNorm(d)
        self.drop = drop
        nn.init.normal_(self.tok.weight, std=0.02)
        nn.init.normal_(self.pos.weight, std=0.01)

    def forward(self, idx):
        x = self.tok(idx) + self.pos(torch.arange(idx.shape[1]))
        x = F.dropout(x, self.drop, self.training)
        for b in self.blocks:
            x = b(x, self.drop)
        return self.lnf(x) @ self.tok.weight.T

    def export(self, L):
        P = {"tok": self.tok.weight, "pos": self.pos.weight, "lnf_g": self.lnf.weight, "lnf_b": self.lnf.bias}
        for i, b in enumerate(self.blocks):
            p = "l%d_" % i
            P.update({p + "ln1_g": b.ln1.weight, p + "ln1_b": b.ln1.bias, p + "ln2_g": b.ln2.weight, p + "ln2_b": b.ln2.bias,
                      p + "qkv_w": b.qkv.weight.T, p + "qkv_b": b.qkv.bias, p + "proj_w": b.proj.weight.T, p + "proj_b": b.proj.bias,
                      p + "fc_w": b.fc.weight.T, p + "fc_b": b.fc.bias, p + "out_w": b.out.weight.T, p + "out_b": b.out.bias})
        return {k: v.detach().numpy().astype(np.float32).copy() for k, v in P.items()}


def load_rows(name):
    with open(os.path.join(SETS, name + ".jsonl"), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def to_symbols(rows):
    """Вопрос и решение → символы N/R (числа.py); неудачные переводы выбрасываются."""
    out = []
    for r in rows:
        q, env = C.question_to_symbols(r["question"])
        a = C.answer_to_symbols(r["answer"], env)
        if a is not None:
            out.append(dict(r, question=q, answer=a))
    return out


def sym_tokenizer(rows, suffix=""):
    """Куски слов для символьного режима: N1..N20, R1..R20 — цельные куски. Учится на своём train один раз."""
    path = os.path.join(SETS, "куски_символы%s.model" % suffix)
    if not os.path.exists(path):
        import io
        import sentencepiece as spm
        lines = []
        for r in rows:
            lines += [r["question"].replace("\n", R.NL), r["answer"].replace("\n", R.NL)]
        buf = io.BytesIO()
        syms = ["<<", ">>", "####", R.NL] + ["N%d" % i for i in range(1, 21)] + ["R%d" % i for i in range(1, 21)]
        spm.SentencePieceTrainer.train(sentence_iterator=iter(lines), model_writer=buf, vocab_size=4000, model_type="bpe",
                                       character_coverage=1.0, split_digits=True, byte_fallback=True, user_defined_symbols=syms,
                                       remove_extra_whitespaces=False, normalization_rule_name="identity", pad_id=0, unk_id=1,
                                       bos_id=2, eos_id=3, num_threads=6, input_sentence_size=2000000, shuffle_input_sentence=True)
        open(path, "wb").write(buf.getvalue())
    return open(path, "rb").read()


def encode(sp, rows):
    out = []
    for r in rows:
        p = R.encode_prompt(sp, r["question"])
        a = sp.encode(r["answer"].replace("\n", R.NL)) + [R.EOS]
        seq = (p + a)[:CTX]
        if len(p) < CTX - 8:
            out.append((seq, len(p)))
    return out


def batches(data, tokens_per_batch, rnd):
    order = sorted(range(len(data)), key=lambda i: (len(data[i][0]), rnd.random()))
    chunks, cur, cur_max = [], [], 0
    for i in order:
        L = len(data[i][0])
        if cur and max(cur_max, L) * (len(cur) + 1) > tokens_per_batch:
            chunks.append(cur)
            cur, cur_max = [], 0
        cur.append(i)
        cur_max = max(cur_max, L)
    if cur:
        chunks.append(cur)
    rnd.shuffle(chunks)
    return chunks


def tensors(data, idx):
    T = max(len(data[i][0]) for i in idx)
    x = torch.zeros((len(idx), T), dtype=torch.long)
    y = torch.full((len(idx), T), -100, dtype=torch.long)
    for r, i in enumerate(idx):
        seq, plen = data[i]
        x[r, :len(seq)] = torch.tensor(seq)
        y[r, plen - 1:len(seq) - 1] = torch.tensor(seq[plen:])
    return x, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--размер", choices=SIZES, default="малый")
    ap.add_argument("--эпох", type=float, default=5)
    ap.add_argument("--токенов_в_пачке", type=int, default=8192)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--зерно", type=int, default=1)
    ap.add_argument("--выход", default=None)
    ap.add_argument("--потоков", type=int, default=6)
    ap.add_argument("--ген", type=int, default=20000, help="сколько задач генератора взять в обучение")
    ap.add_argument("--gsm", type=int, default=1, help="брать ли GSM8K train в обучение (1/0)")
    ap.add_argument("--символы", action="store_true", help="числа как символы (архитектура решатель2)")
    ap.add_argument("--набор", default="train", help="файл обучения в задачи/наборы (train или train2)")
    ap.add_argument("--dev", default="dev")
    a = ap.parse_args()
    torch.set_num_threads(a.потоков)
    try:
        import общее_обучения  # noqa
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class S(ctypes.Structure):
                _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
            k = ctypes.windll.kernel32
            hp = k.GetCurrentProcess()
            s = S(1, 1, 0)
            k.SetProcessInformation(hp, 4, ctypes.byref(s), ctypes.sizeof(s))
            k.SetPriorityClass(hp, 0x8000)
        except Exception:
            pass
    torch.manual_seed(a.зерно)
    rnd = random.Random(a.зерно)
    rows = load_rows(a.набор)
    gen_rows = [r for r in rows if r["источник"].startswith("генератор")][:a.ген]
    rows = gen_rows + ([r for r in rows if r["источник"] == "gsm8k"] if a.gsm else [])
    dev_rows = load_rows(a.dev) if a.gsm else [r for r in load_rows(a.dev) if r["источник"].startswith("генератор")]
    if a.символы:
        rows, dev_rows = to_symbols(rows), to_symbols(dev_rows)
        sp_bytes = sym_tokenizer(to_symbols(load_rows(a.набор)), "" if a.набор == "train" else "_" + a.набор)
    else:
        sp_bytes = open(os.path.join(SETS, "куски.model"), "rb").read()
    sp = R._sp(sp_bytes)
    V = sp.get_piece_size()
    tr, dv = encode(sp, rows), encode(sp, dev_rows)
    cfg = SIZES[a.размер]
    model = GPT(V, cfg["dim"], cfg["слоёв"], cfg["голов"], drop=0.1)
    n_params = sum(p.numel() for p in model.parameters())
    print("параметров %d, обучающих %d, dev %d" % (n_params, len(tr), len(dv)), flush=True)
    steps_per_epoch = len(batches(tr, a.токенов_в_пачке, random.Random(0)))
    total = int(steps_per_epoch * a.эпох)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, betas=(0.9, 0.98), weight_decay=0.05)
    warm = max(1, min(500, total // 20))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / total))))

    def dev_loss():
        model.eval()
        tot, n = 0.0, 0
        with torch.no_grad():
            for idx in batches(dv, a.токенов_в_пачке, random.Random(1)):
                x, y = tensors(dv, idx)
                l = F.cross_entropy(model(x).reshape(-1, V), y.reshape(-1), ignore_index=-100, reduction="sum")
                tot += float(l)
                n += int((y != -100).sum())
        model.train()
        return tot / n

    out_dir = a.выход or os.path.join(V4, "блоки_задачи", "задачи_" + a.размер)
    os.makedirs(out_dir, exist_ok=True)
    t0, step, best, log = time.time(), 0, 1e9, []
    model.train()
    while step < total:
        for idx in batches(tr, a.токенов_в_пачке, rnd):
            if step >= total:
                break
            x, y = tensors(tr, idx)
            loss = F.cross_entropy(model(x).reshape(-1, V), y.reshape(-1), ignore_index=-100)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            step += 1
            if step % 200 == 0 or step == total or (total < 200 and step % 20 == 0):
                dl = dev_loss()
                log.append({"шаг": step, "loss": round(float(loss), 4), "dev": round(dl, 4), "мин": round((time.time() - t0) / 60, 1)})
                print("шаг %d/%d loss %.4f dev %.4f  %.1f мин" % (step, total, float(loss), dl, (time.time() - t0) / 60), flush=True)
                if dl < best:
                    best = dl
                    np.savez(os.path.join(out_dir, "_лучший.npz"), **model.export(cfg["слоёв"]))
    P = dict(np.load(os.path.join(out_dir, "_лучший.npz")))
    os.remove(os.path.join(out_dir, "_лучший.npz"))
    G.save_npz(os.path.join(out_dir, "веса.npz"), dict(P, куски=np.frombuffer(sp_bytes, dtype=np.uint8)))
    ty = Types(os.path.join(V4, "типы"))
    n = int(sum(v.size for v in P.values()))
    ps = {"имя": "задачи", "версия": 1, "область": "задачи", "роль": "решает текстовые задачи и пишет решение по шагам (ru, en)",
          "вход": {"тип": "общие:Направление", "условие": {"область": "задачи"}}, "выход": {"тип": "общие:Ответ"},
          "архитектура": "решатель2" if a.символы else "решатель", "заявка": False,
          "настройки": {"dim": cfg["dim"], "слоёв": cfg["слоёв"], "голов": cfg["голов"], "контекст": CTX, "калькулятор": True,
                        "макс_кусков": 300 if a.символы else 400, "числа_символами": bool(a.символы)},
          "веса": {"файл": "веса.npz", "sha256": sha256_file(os.path.join(out_dir, "веса.npz")), "чисел": n},
          "типы": {"общие:Направление": ty.fingerprint("общие:Направление"), "общие:Ответ": ty.fingerprint("общие:Ответ")},
          "обучение": {"скрипт": "обучение/обучить_решатель.py", "размер": a.размер, "зерно": a.зерно, "эпох": a.эпох, "шагов": total,
                       "данные": "задачи/наборы/%s.jsonl: генератор %d%s%s" % (a.набор, a.ген, " + GSM8K ru/en" if a.gsm else "", ", числа символами" if a.символы else ""), "строк": len(tr), "лучший_dev_loss": round(best, 4),
                       "время_мин": round((time.time() - t0) / 60, 1), "журнал": log,
                       "когда": datetime.datetime.now().isoformat(timespec="seconds")}}
    with open(os.path.join(out_dir, "паспорт.json"), "w", encoding="utf-8") as f:
        json.dump(ps, f, ensure_ascii=False, indent=1)
    print("записан", out_dir, "чисел", n, "лучший dev", round(best, 4))


if __name__ == "__main__":
    main()
