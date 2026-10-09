# -*- coding: utf-8 -*-
"""Собирает блок «здоровье.прил» из модели приложения (research/engine_py.py PyEngine, M+ambig) — без переобучения:
обученные числа копируются как есть, проверяется паритет вероятностей с исходным движком на 293 тестовых вопросах.
Проект только читается. Запуск (venv проекта): train/.venv/Scripts/python.exe собрать_блок_приложения.py"""
import json
import os
import sys

sys.dont_write_bytecode = True
V5 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, V5)
sys.path.insert(0, os.path.join(V5, "архитектуры"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import numpy as np  # noqa: E402

import общее as G  # noqa: E402
import приложение as A  # noqa: E402
from ядро.схема import Types, sha256_file  # noqa: E402

sys.path.insert(0, os.path.join(A.PROJECT, "research"))
from engine_py import PyEngine  # noqa: E402

OUT = os.path.join(V5, "блоки", "здоровье.прил")


def main():
    E = PyEngine(ambig=True)
    ai = {d["article_no"]: i for i, d in enumerate(E.docs)}
    phrases = [{"text": q["text"], "article_no": q["article_no"]} for q in E.sets["lay_train"] + E.sets["t_train"]]
    from core_v3 import short_doc_items
    from claude_ambiguous import AMBIGUOUS
    mem = [(q["text"], ai[q["article_no"]]) for q in phrases] + short_doc_items(E.docs) + [(t, ai[str(x)]) for t, arts in AMBIGUOUS for x in arts]
    assert len(mem) == len(E.ML) and all(int(a) == int(b) for (_, a), b in zip(mem, E.ML))
    data = {"docs": E.docs, "phrases": phrases, "mem": mem, "sig": list(E.sig)}
    arrays = {"ew": E.m.ew.weight.detach().numpy().astype(np.float32), "ec": E.m.ec.weight.detach().numpy().astype(np.float32),
              "crumb_W1": np.asarray(E.c.W1), "crumb_b1": np.asarray(E.c.b1), "crumb_w2": np.asarray(E.c.w2),
              "crumb_b2": np.array([float(E.c.b2)]), "tau": np.array([float(E.tau)]), "thr": np.array([float(E.thr)]),
              "данные": np.frombuffer(json.dumps(data, ensure_ascii=False).encode("utf-8"), dtype=np.uint8),
              "словарь": np.frombuffer(json.dumps({"w": E.v.w, "c": E.v.c}, ensure_ascii=False).encode("utf-8"), dtype=np.uint8)}
    os.makedirs(OUT, exist_ok=True)
    w = os.path.join(OUT, "веса.npz")
    G.save_npz(w, arrays)
    n = int(sum(arrays[k].size for k in ("ew", "ec", "crumb_W1", "crumb_b1", "crumb_w2", "crumb_b2", "tau", "thr")))
    ty = Types(os.path.join(V5, "типы"))
    arts = [d["article_no"] for d in E.docs]
    ps = {"имя": "здоровье.прил", "версия": 1, "область": "здоровье",
          "роль": "знание области «здоровье» — модель приложения справочника (TINY 1.6, M+ambig): BM25 + память фраз + крошка",
          "вход": {"тип": "общие:Направление", "условие": {"область": "здоровье"}}, "выход": {"тип": "общие:Ответ"},
          "архитектура": "приложение", "заявка": False, "ответы": arts,
          "настройки": {"код_sha256": A.code_hashes(), "сигналы": list(E.sig)},
          "веса": {"файл": "веса.npz", "sha256": sha256_file(w), "чисел": n},
          "память": {"записей": len(mem), "фраз_для_BM25": len(phrases)},
          "типы": {"общие:Направление": ty.fingerprint("общие:Направление"), "общие:Ответ": ty.fingerprint("общие:Ответ")},
          "контроль": {"файл": "контроль.jsonl"},
          "обучение": {"откуда": "research/engine_py.py PyEngine(ambig=True): train/models/net_v3_ambig.pt, train/cache/crumbs_v3_ambig.pkl",
                       "переобучение": "нет — числа скопированы как есть", "источник_sha256": {
                           "net_v3_ambig.pt": sha256_file(os.path.join(A.TRAIN, "models", "net_v3_ambig.pt")),
                           "crumbs_v3_ambig.pkl": sha256_file(os.path.join(A.TRAIN, "cache", "crumbs_v3_ambig.pkl"))}}}
    ctrl = [q for q in E.sets["lay_dev"]][:60]
    with open(os.path.join(OUT, "контроль.jsonl"), "w", encoding="utf-8") as f:
        for q in ctrl:
            f.write(json.dumps({"запрос": q["text"], "ожидание": {"область": "здоровье"}}, ensure_ascii=False) + "\n")
    with open(os.path.join(OUT, "паспорт.json"), "w", encoding="utf-8") as f:
        json.dump(ps, f, ensure_ascii=False, indent=1)
    # паритет с исходным движком
    obj = A.load(w, ps, None)
    bench = [json.loads(l) for l in open(r"C:\ЯДРО-ОПЫТ\bench\bench.jsonl", encoding="utf-8")]
    texts = [r["вопрос"] for r in bench if r["область"] == "здоровье"]
    d = float(np.abs(np.asarray(E.probs(texts)) - A.probs(obj, texts)).max())
    print("записан", OUT, "| обученных чисел", n, "| записей памяти", len(mem), "| паритет с движком приложения: макс. разница %.2e" % d)


if __name__ == "__main__":
    main()
