# -*- coding: utf-8 -*-
"""Блок-решатель задач (код без весов): маленький трансформер-декодер, пишет решение по шагам кусками слов.
Вход: общие:Направление[область=задачи] (или просто текст). Выход: общие:Ответ вид «текст» (текст решения, итог — число).
Вывод — жадный, детерминированный, на numpy с кэшем ключей/значений.
Калькулятор (по настройке «калькулятор»): когда сеть написала «<<выражение=», код считает выражение и дописывает
«результат>>» — сеть решает, ЧТО считать, код — считает. Без калькулятора числа пишет сама сеть,
а неверный шаг ловит проверка типа общие:Ответ (ядро тогда скажет «не знаю»)."""
import ast
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as G  # noqa: E402

NL = "⏎"
EOS = 3
_OPEN = re.compile(r"<<([^<>=]*)=$")


# ---------------- куски слов ----------------
def _sp(model_bytes):
    import sentencepiece as spm
    return spm.SentencePieceProcessor(model_proto=model_bytes)


def encode_prompt(sp, question):
    return sp.encode(question.replace("\n", NL)) + sp.encode(NL + NL)


# ---------------- калькулятор ----------------
def _ev(n):
    if isinstance(n, ast.Expression):
        return _ev(n.body)
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return n.value
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
        return -_ev(n.operand)
    if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        a, b = _ev(n.left), _ev(n.right)
        return a + b if isinstance(n.op, ast.Add) else a - b if isinstance(n.op, ast.Sub) else a * b if isinstance(n.op, ast.Mult) else a / b
    raise ValueError


def calculate(expr):
    try:
        v = _ev(ast.parse(expr.replace(" ", "").replace(",", ""), mode="eval"))
    except Exception:  # noqa: BLE001
        return None
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ("%.4f" % v).rstrip("0").rstrip(".")


# ---------------- сеть (numpy) ----------------
def _ln(x, g, b):
    m = x.mean(-1, keepdims=True)
    v = ((x - m) ** 2).mean(-1, keepdims=True)
    return (x - m) / np.sqrt(v + 1e-5) * g + b


def _gelu(x):
    return 0.5 * x * (1.0 + np.tanh(0.7978845608 * (x + 0.044715 * x ** 3)))


class Runner:
    def __init__(self, P, cfg):
        self.P, self.L, self.H = P, cfg["слоёв"], cfg["голов"]
        self.d = P["tok"].shape[1]
        self.reset()

    def reset(self):
        self.k = [np.zeros((self.H, 0, self.d // self.H), np.float32) for _ in range(self.L)]
        self.v = [np.zeros((self.H, 0, self.d // self.H), np.float32) for _ in range(self.L)]
        self.t = 0

    def step(self, toks):
        """Подать куски (список id), вернуть логиты последнего."""
        P, H, d = self.P, self.H, self.d
        hd = d // H
        n = len(toks)
        x = P["tok"][toks] + P["pos"][self.t:self.t + n]
        for i in range(self.L):
            p = "l%d_" % i
            h = _ln(x, P[p + "ln1_g"], P[p + "ln1_b"])
            qkv = h @ P[p + "qkv_w"] + P[p + "qkv_b"]
            q, k, v = np.split(qkv, 3, axis=-1)
            q = q.reshape(n, H, hd).transpose(1, 0, 2)
            k = k.reshape(n, H, hd).transpose(1, 0, 2)
            v = v.reshape(n, H, hd).transpose(1, 0, 2)
            self.k[i] = np.concatenate([self.k[i], k], 1)
            self.v[i] = np.concatenate([self.v[i], v], 1)
            att = q @ self.k[i].transpose(0, 2, 1) / np.sqrt(hd)
            T = self.k[i].shape[1]
            mask = np.triu(np.ones((n, T), bool), k=T - n + 1)
            att = np.where(mask, -1e9, att)
            att = np.exp(att - att.max(-1, keepdims=True))
            att /= att.sum(-1, keepdims=True)
            o = (att @ self.v[i]).transpose(1, 0, 2).reshape(n, d)
            x = x + o @ P[p + "proj_w"] + P[p + "proj_b"]
            h = _ln(x, P[p + "ln2_g"], P[p + "ln2_b"])
            x = x + _gelu(h @ P[p + "fc_w"] + P[p + "fc_b"]) @ P[p + "out_w"] + P[p + "out_b"]
        self.t += n
        x = _ln(x[-1:], P["lnf_g"], P["lnf_b"])
        return (x @ P["tok"].T)[0]


def solve(obj, question, max_new=None):
    """Жадное решение. Возвращает (текст решения, итог или None)."""
    sp, cfg = obj["sp"], obj["cfg"]
    max_new = max_new or cfg.get("макс_кусков", 400)
    ctx = cfg["контекст"]
    r = obj["runner"]
    r.reset()
    prompt = encode_prompt(sp, question)[-(ctx // 2):]
    logits = r.step(prompt)
    out = []
    while len(out) < max_new and r.t < ctx:
        t = int(np.argmax(logits))
        if t == EOS:
            break
        out.append(t)
        feed = [t]
        if cfg.get("калькулятор"):
            text = sp.decode(out)
            m = _OPEN.search(text)
            if m:
                res = calculate(m.group(1))
                if res is not None:
                    extra = sp.encode(res + ">>")
                    if extra and sp.id_to_piece(extra[0]) == "▁":   # без пробела после «=»
                        extra = extra[1:]
                    out += extra
                    feed += extra
        if r.t + len(feed) > ctx:
            break
        logits = r.step(feed)
        text = sp.decode(out)
        if "####" in text and re.search(r"####\s*-?[\d.,]+\s*$", text) and len(out) >= 2 and sp.id_to_piece(out[-1]) == NL:
            break
    text = sp.decode(out).replace(NL, "\n").strip()
    m = re.search(r"####\s*(-?[\d.,]+)", text)
    final = m.group(1).replace(",", "").rstrip(".") if m else None
    return text, final


# ---------------- интерфейс блока ----------------
def load(path, passport, types_dir):
    P = G.load_npz(path)
    sp_bytes = P.pop("куски").tobytes()
    obj = {"P": P, "sp_bytes": sp_bytes, "sp": _sp(sp_bytes), "cfg": passport["настройки"], "area": passport["область"]}
    obj["runner"] = Runner(P, obj["cfg"])
    return obj


def interface(obj):
    return {}


def run(obj, value):
    q = value["текст"] if isinstance(value, dict) else value
    text, final = solve(obj, q)
    out = {"область": obj["area"], "вид": "текст", "текст": text, "p": 1.0}
    if final is not None:
        out["итог"] = final
    return out


def params(obj):
    return dict(obj["P"])


def save(P, obj, path):
    G.save_npz(path, dict(P, куски=np.frombuffer(obj["sp_bytes"], dtype=np.uint8)))
