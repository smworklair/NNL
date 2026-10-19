# -*- coding: utf-8 -*-
"""Починка 2: Б1 (заявка v2), Б3а (заявка v3), Б3 (заявка v3 + пороги уверенности знаний). Те же наборы, что в замер2.
Пишет результаты/замер3.json. Запуск: python замер3.py"""
import json, os, sys
sys.dont_write_bytecode = True
import замер2 as Z
Z.SYS = {"Б1": (["здоровье.заявка2", "здоровье.прил", "право.заявка", "право"], False),
         "Б3а": (["здоровье.заявка3", "здоровье.прил", "право.заявка", "право"], False),
         "Б3": (["здоровье.заявка3", "здоровье.прил2", "право.заявка", "право2"], False)}
orig = Z.json.dump
def dump(obj, f, **kw):
    f.close()
    return orig(obj, open(os.path.join(Z.V5, "результаты", "замер3.json"), "w", encoding="utf-8"), **kw)
Z.json.dump = dump
Z.main()
