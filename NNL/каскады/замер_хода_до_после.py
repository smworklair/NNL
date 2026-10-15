# -*- coding: utf-8 -*-
"""Живой замер хода (настоящие вызовы API, как диалог/замер_хода.py) для ядра учёта «до» (замороженное) и «после» (рабочее). Сам замер_хода.py не меняется:
берётся его функция прогон() на сценариях бенчмарка с банком вопросов, без кэша. Ничего не пишется в ~/.nnl/кэш_моделей.jsonl (вызовы идут с кэш=False).
Нужен ключ провайдера (по умолчанию alibaba:qwen3.8-flash). Ответы модели от запуска к запуску немного разные: сравнивайте с оглядкой на этот разброс.
Запуск: python NNL/каскады/замер_хода_до_после.py до|после [провайдер:модель]"""
import json
import os
import sys

КАТАЛОГ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(КАТАЛОГ), "диалог"))
sys.path.insert(0, КАТАЛОГ)
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import бенч as Б  # noqa: E402
import диалог as Д  # noqa: E402
import замер_хода as ЗХ  # noqa: E402
import стенд_диалога as СД  # noqa: E402

if __name__ == "__main__":
    профиль = sys.argv[1] if len(sys.argv) > 1 else "после"
    модель = sys.argv[2] if len(sys.argv) > 2 else "alibaba:qwen3.8-flash"
    СД.применить_профиль(профиль)
    система = Д.Система()
    print("профиль «%s», модель %s, статей в банке: %s" % (профиль, модель, len(система.банк.актуальные) if система.банк else "банка нет"))
    итого = ЗХ.прогон(система, Б._роли_кандидата(модель), "ядро учёта: %s" % профиль)
    print(json.dumps({"профиль": профиль, "модель": модель, **итого}, ensure_ascii=False))
