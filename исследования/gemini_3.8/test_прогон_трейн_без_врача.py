# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from данные_кейсы import получить_выборку
from режим_ядро import РежимЯдро
from режим_агент import РежимАгент
from валидатор import ВалидаторЯдра

train_cases = получить_выборку(только_тест=False)
case_no_doc = [c for c in train_cases if not c["врач_подтвердил"]][0]
print(f"Тестируем на кейсе настройки БЕЗ ВРАЧА: {case_no_doc['id']} (ст. {case_no_doc['истинная_статья']}, врач={case_no_doc['врач_подтвердил']})")

валидатор = ВалидаторЯдра()

print("\n--- Запуск Режима Ядро ---")
core_runner = РежимЯдро()
core_res = core_runner.выполнить(case_no_doc)
core_passed, core_reason, _ = валидатор.валидировать(core_res["текст_ответа"], core_res["статьи"], case_no_doc)
print("Ядро ответ:\n", core_res["текст_ответа"][:200], "...")
print("Ядро принято:", core_passed, "Причина:", core_reason)
print("Статистика ядра:", core_res["статистика"])

print("\n--- Запуск Режима Агент-Детектив ---")
agent_runner = РежимАгент()
agent_res = agent_runner.выполнить(case_no_doc)
agent_passed, agent_reason, _ = валидатор.валидировать(agent_res["текст_ответа"], agent_res["статьи"], case_no_doc)
print("Агент ответ:\n", agent_res["текст_ответа"][:200], "...")
print("Агент принято:", agent_passed, "Причина:", agent_reason)
print("Статистика агента:", agent_res["статистика"])
