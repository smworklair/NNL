# -*- coding: utf-8 -*-
"""Запись блока на диск: веса.npz + паспорт.json (sha256 весов и типов вписываются сюда)."""
import datetime
import json
import os
import sys

V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TYPES_DIR = os.path.join(V3, "типы")
ARCH_DIR = os.path.join(V3, "архитектуры")
sys.path.insert(0, V3)
sys.path.insert(0, ARCH_DIR)

from ядро.типы import sha256_file  # noqa: E402
import общее as G  # noqa: E402


def unthrottle():
    """Windows 11 душит фоновые процессы (EcoQoS) — снимаем для своего процесса."""
    if sys.platform != "win32":
        return
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


def types_sha():
    return sha256_file(os.path.join(TYPES_DIR, "типы.json"))


def write_block(out_dir, passport, arrays):
    os.makedirs(out_dir, exist_ok=True)
    wfile = os.path.join(out_dir, "веса.npz")
    G.save_npz(wfile, arrays)
    n = sum(int(v.size) for k, v in arrays.items() if v.dtype.kind == "f")
    passport = dict(passport)
    passport["веса"] = {"файл": "веса.npz", "sha256": sha256_file(wfile), "чисел": n}
    passport["типы_sha256"] = types_sha()
    passport.setdefault("родитель", None)
    passport["обучение"]["когда"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(os.path.join(out_dir, "паспорт.json"), "w", encoding="utf-8") as f:
        json.dump(passport, f, ensure_ascii=False, indent=1)
    print("записан", out_dir, "чисел:", n)
    return passport
