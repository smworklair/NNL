# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from данные_кейсы import получить_выборку
from режим_агент import РежимАгент
from валидатор import ВалидаторЯдра

case = получить_выборку(True)[0]
print(f"Running agent on {case['id']}...")
runner = РежимАгент(модель="qwen/qwen3.8-27b")
res = runner.выполнить(case)

валидатор = ВалидаторЯдра()
passed, reason, _ = валидатор.валидировать(res["текст_ответа"], res["статьи"], case)
print("Response:\n", res["текст_ответа"][:150], "...")
print("Passed:", passed, "Reason:", reason)
print("Stats:", res["статистика"])
