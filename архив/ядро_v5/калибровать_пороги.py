# -*- coding: utf-8 -*-
"""Порог уверенности знания: 5 %-квантиль p верных ответов блока на СВОЁМ dev. Новые версии паспортов, веса те же.
  здоровье.прил → здоровье.прил2 (dev: вопросы учителя dev_t — lay dev приложение видело при обучении крошки)
  право → право2 (dev: lex dev). Запуск: python калибровать_пороги.py"""
import json, os, shutil, sys
sys.dont_write_bytecode = True
V5 = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V5)
import numpy as np
from ядро import Kernel
from обучение import данные
ROOT = r"C:\ВОЕНКОМАТ ПРОЕКТ НАВЗВАНИЕ НЕ ПРИДУМАЛ"

def dev(area):
    if area == "здоровье":
        return [(json.loads(l)["text"], json.loads(l)["article_no"]) for l in open(os.path.join(ROOT, "train/data/queries_claude_teacher.jsonl"), encoding="utf-8")
                if json.loads(l)["split"] == "dev_t"]
    return данные.domain_data("право", "dev")

k = Kernel(os.path.join(V5, "типы"), os.path.join(V5, "архитектуры"))
for src, dst, area in (("здоровье.прил", "здоровье.прил2", "здоровье"), ("право", "право2", "право")):
    k.attach(os.path.join(V5, "блоки", src))
    b = k.blocks[src]
    rows = dev(area)
    outs = [b.arch.run(b.obj, {"область": area, "текст": t}) for t, _ in rows]
    ok_p = np.array([o["p"] for o, (_, y) in zip(outs, rows) if o["id"] == y])
    bad_p = np.array([o["p"] for o, (_, y) in zip(outs, rows) if o["id"] != y])
    thr = float(np.quantile(ok_p, 0.05))
    d = os.path.join(V5, "блоки", dst)
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(os.path.join(V5, "блоки", src), d)
    ps = json.load(open(os.path.join(d, "паспорт.json"), encoding="utf-8"))
    ps["имя"], ps["порог_ответа"] = dst, round(thr, 6)
    ps["калибровка_ответа"] = {"dev": "учитель dev_t" if area == "здоровье" else "lex dev", "строк": len(rows), "верных": int(len(ok_p)),
                               "правило": "5 %-квантиль p верных ответов", "неверных_ниже_порога": "%d/%d" % (int((bad_p < thr).sum()), len(bad_p))}
    json.dump(ps, open(os.path.join(d, "паспорт.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(dst, "порог %.4f" % thr, ps["калибровка_ответа"])
    k.detach(src)
