# -*- coding: utf-8 -*-
"""Блок-решатель v2 (код без весов): числа как символы (см. числа.py).
Вопрос → числа заменены на N1, N2…; сеть пишет решение символами; когда сеть написала «<<выражение=», код считает
выражение по значениям символов и дописывает «Rk>>». В конце символы заменяются числами — получается обычное
решение GSM8K-вида (<<5*3=15>>15 … #### 18), его проверяет тип общие:Ответ.
Вход: общие:Направление[область=задачи]. Выход: общие:Ответ вид «текст» (итог — число)."""
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import общее as G  # noqa: E402
import решатель as R1  # noqa: E402  (сеть Runner и куски слов — те же)
import числа as C  # noqa: E402

NL, EOS = R1.NL, R1.EOS
_OPEN = re.compile(r"<<([^<>=]*)=$")


def encode_prompt(sp, question_sym):
    return sp.encode(question_sym.replace("\n", NL)) + sp.encode(NL + NL)


def solve(obj, question, max_new=None):
    sp, cfg, r = obj["sp"], obj["cfg"], obj["runner"]
    max_new = max_new or cfg.get("макс_кусков", 300)
    ctx = cfg["контекст"]
    qs, env = C.question_to_symbols(question)
    r.reset()
    logits = r.step(encode_prompt(sp, qs)[-(ctx // 2):])
    out, n_res = [], 0
    while len(out) < max_new and r.t < ctx:
        t = int(np.argmax(logits))
        if t == EOS:
            break
        out.append(t)
        feed = [t]
        m = _OPEN.search(sp.decode(out))
        if m:
            v = C.eval_expr(m.group(1), env)
            if v is not None and n_res < C.MAX_SYM:
                n_res += 1
                rs = "R%d" % n_res
                env[rs] = v
                extra = sp.encode(rs + ">>")
                if extra and sp.id_to_piece(extra[0]) == "▁":
                    extra = extra[1:]
                out += extra
                feed += extra
        if r.t + len(feed) > ctx:
            break
        logits = r.step(feed)
    sym_text = sp.decode(out).replace(NL, "\n").strip()
    m = re.search(r"####\s*([NR]\d+|-?\d+(?:[.,]\d+)?)", sym_text)
    final = None
    if m:
        tok = m.group(1)
        if tok in env:
            final = C.fmt(env[tok])
        elif C.NUM.fullmatch(tok):
            final = C.fmt(C.value(tok))
    return C.render(sym_text, env), final, sym_text


def load(path, passport, types_dir):
    P = G.load_npz(path)
    sp_bytes = P.pop("куски").tobytes()
    obj = {"P": P, "sp_bytes": sp_bytes, "sp": R1._sp(sp_bytes), "cfg": passport["настройки"], "area": passport["область"]}
    obj["runner"] = R1.Runner(P, obj["cfg"])
    return obj


def interface(obj):
    return {}


def run(obj, value):
    q = value["текст"] if isinstance(value, dict) else value
    text, final, _ = solve(obj, q)
    out = {"область": obj["area"], "вид": "текст", "текст": text, "p": 1.0}
    if final is not None:
        out["итог"] = final
    return out


def params(obj):
    return dict(obj["P"])


def save(P, obj, path):
    G.save_npz(path, dict(P, куски=np.frombuffer(obj["sp_bytes"], dtype=np.uint8)))
