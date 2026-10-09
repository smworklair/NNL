# -*- coding: utf-8 -*-
"""Починка 3: Б3а и Б4 (заявка v3 + своё «ничего» приложения + порог права). Пишет результаты/замер4.json."""
import os, sys
sys.dont_write_bytecode = True
import замер2 as Z
Z.SYS = {"Б3а": (["здоровье.заявка3", "здоровье.прил", "право.заявка", "право"], False),
         "Б4а": (["здоровье.заявка3", "здоровье.прил3", "право.заявка", "право"], False),
         "Б4": (["здоровье.заявка3", "здоровье.прил3", "право.заявка", "право2"], False)}
orig = Z.json.dump
def dump(obj, f, **kw):
    f.close()
    return orig(obj, open(os.path.join(Z.V5, "результаты", "замер4.json"), "w", encoding="utf-8"), **kw)
Z.json.dump = dump
Z.main()
