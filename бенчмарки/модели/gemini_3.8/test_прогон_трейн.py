# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from данные_кейсы import получить_выборку
from режим_ядро import РежимЯдро
from режим_агент import РежимАгент
from валидатор import ВалидаторЯдра

train_cases = получить_выборку(только_тест=False)
case0 = train_cases[0]
print(f"Тестируем на кейсе настройки: {case0['id']} (ст. {case0['истинная_статья']}, врач={case0['врач_подтвердил']})")

валидатор = ВалидаторЯдра()

print("\n--- Запуск Режима Ядро ---")
core_runner = РежимЯдро()
core_res = core_runner.выполнить(case0)
core_passed, core_reason, _ = валидатор.валидировать(core_res["текст_ответа"], core_res["статьи"], case0)
print("Ядро ответ:", core_res["текст_ответа"][:150], "...")
print("Ядро принято:", core_passed, "Причина:", core_reason)
print("Статистика ядра:", core_res["статистика"])

print("\n--- Запуск Режима Агент-Детектив ---")
agent_runner = РежимАгент()
agent_res = agent_runner.выполнить(case0)
agent_passed, agent_reason, _ = валидатор.валидировать(agent_res["текст_ответа"], agent_res["статьи"], case0)
print("Агент ответ:", agent_res["текст_ответа"][:150], "...")
print("Агент принято:", agent_passed, "Причина:", agent_reason)
print("Статистика агента:", agent_res["статистика"])
