# -*- coding: utf-8 -*-
"""Модуль математической оценки инвариантов и симметрий в NNL.
Измеряет нарушения как на уровне извлечения фактов LLM, так и на уровне состояния математического ядра.
"""
import math
import os
import re
import sys

sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\NNL\диалог")
import диалог as Д
import знания as З
import расследование as Р

L_ПРИОР = Р.logit(Р.ПРИОР)


def wilson_interval(k, n, z=1.96):
    """95% доверительный интервал Вильсона для биномиальной пропорции."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + (z ** 2) / n
    centre = (p + (z ** 2) / (2 * n)) / denom
    spread = z * math.sqrt((p * (1 - p) + (z ** 2) / (4 * n)) / n) / denom
    lower = max(0.0, centre - spread)
    upper = min(1.0, centre + spread)
    return (round(lower, 4), round(upper, 4))


def прогнать_ядро(система, упоминания):
    """Строгое применение правил NNL (диалог.py + расследование.py) к фактам."""
    cp = Р.Расследование(list(система.база.статьи))
    for у in упоминания:
        термин = str(у.get("термин", "")).strip()
        статус = str(у.get("статус", "есть")).strip()
        уточнение = str(у.get("уточнение", "")).strip()
        кто = str(у.get("кто_подтвердил", "нет_данных")).strip()
        фраза = (термин + " " + уточнение).strip()
        p_статей, p0 = система.блоки.статьи(фраза)
        cp.учесть_упоминание(термин, статус, уточнение, p_статей, p0, кто)

    # Проверка разрешенных чисел по логике NNL
    числа_улик = set()
    for у in cp.улики:
        if у.get("тип") == "упоминание":
            числа_улик |= З.нормализованные_числа(str(у.get("уточнение", "")))

    кандидаты = cp.кандидаты(порог=0.01, n=3)
    top1 = кандидаты[0][0] if кандидаты else None

    # Допуск категоризации врачом (правило NNL: только при подтверждении врача для активного статуса)
    врач_подтвердил = any(
        u.get("подтверждено") == "врач" for u in cp.улики
        if u.get("тип") == "упоминание" and u.get("статус") == "есть"
    )

    return {
        "l": dict(cp.l),
        "top1": top1,
        "улики": list(cp.улики),
        "числа_улик": числа_улик,
        "врач_подтвердил": врач_подтвердил
    }


def извлечь_числа(текст):
    return З.нормализованные_числа(str(текст))


def сопоставить_статью_упоминания(система, термин, уточнение=""):
    """Определяет, к какой статье Расписания блок относит упомянутый факт."""
    фраза = (str(термин) + " " + str(уточнение)).strip()
    p_статей, _ = система.блоки.статьи(фраза)
    if not p_статей:
        return None
    лучшая = max(p_статей.items(), key=lambda x: x[1])
    return лучшая[0]


def оценить_кейс(система, case, разборщик):
    """Оценивает один тестовый случай по всем 8 трансформациям."""
    art1, art2 = case["art1"], case["art2"]
    val1 = case["fact1_val"]
    val1_norm = З.норм_число(val1) if val1 else ""

    # 1. Базовый вариант (orig)
    res_orig = разборщик(case["orig"])
    core_orig = прогнать_ядро(система, res_orig.get("упоминания", []))

    # 2. T1: Перестановка порядка (коммутативность)
    res_t1 = разборщик(case["t1_perm"])
    core_t1 = прогнать_ядро(система, res_t1.get("упоминания", []))
    # Нарушение фактов T1: изменилось число фактов или пропал один из диагнозов
    t1_facts_orig = {
        (сопоставить_статью_упоминания(система, u.get("термин"), u.get("уточнение")), u.get("статус"), u.get("кто_подтвердил"))
        for u in res_orig.get("упоминания", [])
    }
    t1_facts_perm = {
        (сопоставить_статью_упоминания(система, u.get("термин"), u.get("уточнение")), u.get("статус"), u.get("кто_подтвердил"))
        for u in res_t1.get("упоминания", [])
    }
    t1_fact_err = (len(res_orig.get("упоминания", [])) != len(res_t1.get("упоминания", []))) or (t1_facts_orig != t1_facts_perm)
    # Нарушение ядра T1: максимальная дельта лог-шансов > 0.10 или смена top-1
    max_dl_t1 = max(abs(core_orig["l"][a] - core_t1["l"][a]) for a in core_orig["l"])
    t1_core_err = (max_dl_t1 > 0.10) or (core_orig["top1"] != core_t1["top1"])

    # 3. T2: Запись величин словами (нормализация чисел)
    res_t2 = разборщик(case["t2_units"])
    core_t2 = прогнать_ядро(система, res_t2.get("упоминания", []))
    # Нарушение фактов T2: число не нормализовано цифрами в уточнении
    if val1_norm:
        t2_fact_err = val1_norm not in core_t2["числа_улик"]
    else:
        t2_fact_err = len(res_t2.get("упоминания", [])) < len(res_orig.get("упоминания", []))
    # Нарушение ядра T2: отсутствие числа в уликах (guard-сбой) или расхождение лог-шансов
    max_dl_t2 = max(abs(core_orig["l"][a] - core_t2["l"][a]) for a in core_orig["l"])
    t2_core_err = (max_dl_t2 > 0.10) or (val1_norm and val1_norm not in core_t2["числа_улик"])

    # 4. T3: Речевой шум (вежливость, преамбула)
    res_t3 = разборщик(case["t3_noise"])
    core_t3 = прогнать_ядро(система, res_t3.get("упоминания", []))
    t3_facts_noise = {
        (сопоставить_статью_упоминания(система, u.get("термин"), u.get("уточнение")), u.get("статус"), u.get("кто_подтвердил"))
        for u in res_t3.get("упоминания", [])
    }
    t3_fact_err = (len(res_t3.get("упоминания", [])) != len(res_orig.get("упоминания", []))) or (t1_facts_orig != t3_facts_noise)
    max_dl_t3 = max(abs(core_orig["l"][a] - core_t3["l"][a]) for a in core_orig["l"])
    t3_core_err = (max_dl_t3 > 0.10) or (core_orig["top1"] != core_t3["top1"])

    # 5. T4: Самодиагностика (врач vs сам)
    res_t4 = разборщик(case["t4_self"])
    core_t4 = прогнать_ядро(система, res_t4.get("упоминания", []))
    # Нарушение фактов T4: модель извлекла "врач" при явном "сам"
    t4_has_doc = any(u.get("кто_подтвердил") == "врач" for u in res_t4.get("упоминания", []))
    t4_fact_err = t4_has_doc
    # Нарушение безопасности ядра T4: ядро посчитало активный диагноз подтвержденным врачом
    t4_core_err = core_t4["врач_подтвердил"]

    # 6. T5a: Отрицание (статус "нет")
    res_t5a = разборщик(case["t5a_neg"])
    core_t5a = прогнать_ядро(система, res_t5a.get("упоминания", []))
    # Нарушение фактов T5a: отрицаемый симптом art2 помечен как "есть" (галлюцинация наличия)
    t5a_fact_err = any(
        сопоставить_статью_упоминания(система, u.get("термин"), u.get("уточнение")) == art2 and u.get("статус") == "есть"
        for u in res_t5a.get("упоминания", [])
    )
    # Нарушение ядра T5a: лог-шансы статьи 2 не понизились ниже приорного уровня
    t5a_core_err = (core_t5a["l"].get(art2, L_ПРИОР) >= L_ПРИОР)

    # 7. T5b: Анамнез (статус "было")
    res_t5b = разборщик(case["t5b_past"])
    core_t5b = прогнать_ядро(система, res_t5b.get("упоминания", []))
    # Нарушение фактов T5b: детский/прошедший симптом помечен как текущий "есть"
    t5b_fact_err = any(
        сопоставить_статью_упоминания(система, u.get("термин"), u.get("уточнение")) == art2 and u.get("статус") == "есть"
        for u in res_t5b.get("упоминания", [])
    )
    # Нарушение ядра T5b: обновление лог-шансов не масштабировано с весом 0.5 (дельта равна или больше orig)
    delta_orig = core_orig["l"].get(art2, L_ПРИОР) - L_ПРИОР
    delta_past = core_t5b["l"].get(art2, L_ПРИОР) - L_ПРИОР
    t5b_core_err = (delta_orig > 0.5 and delta_past >= delta_orig - 0.05)

    # 8. T5c: Чужое лицо (статус "чужое")
    res_t5c = разборщик(case["t5c_other"])
    core_t5c = прогнать_ядро(система, res_t5c.get("упоминания", []))
    # Нарушение фактов T5c: чужой симптом помечен как "есть" у призывника
    t5c_fact_err = any(
        сопоставить_статью_упоминания(система, u.get("термин"), u.get("уточнение")) == art2 and u.get("статус") == "есть"
        for u in res_t5c.get("упоминания", [])
    )
    # Нарушение ядра T5c: чужой симптом сместил лог-шансы статьи art2 от приора
    t5c_core_err = abs(core_t5c["l"].get(art2, L_ПРИОР) - L_ПРИОР) > 1e-4

    return {
        "case_id": case["id"],
        "T1_perm": {"fact_err": t1_fact_err, "core_err": t1_core_err, "max_dl": round(max_dl_t1, 4)},
        "T2_units": {"fact_err": t2_fact_err, "core_err": t2_core_err, "val1": val1_norm, "found": list(core_t2["числа_улик"])},
        "T3_noise": {"fact_err": t3_fact_err, "core_err": t3_core_err, "max_dl": round(max_dl_t3, 4)},
        "T4_self": {"fact_err": t4_fact_err, "core_err": t4_core_err},
        "T5a_neg": {"fact_err": t5a_neg_err if 't5a_neg_err' in locals() else t5a_fact_err, "core_err": t5a_core_err},
        "T5b_past": {"fact_err": t5b_fact_err, "core_err": t5b_core_err},
        "T5c_other": {"fact_err": t5c_fact_err, "core_err": t5c_core_err}
    }


def агрегировать_результаты(результаты_кейсов):
    """Считает доли ошибок и доверительные интервалы по выборке."""
    n = len(результаты_кейсов)
    трансформации = ["T1_perm", "T2_units", "T3_noise", "T4_self", "T5a_neg", "T5b_past", "T5c_other"]
    сводка = {}
    for t in трансформации:
        fact_errs = sum(1 for r in результаты_кейсов if r[t]["fact_err"])
        core_errs = sum(1 for r in результаты_кейсов if r[t]["core_err"])
        сводка[t] = {
            "n": n,
            "fact_errs": fact_errs,
            "fact_err_rate": round(fact_errs / n, 4),
            "fact_ci": wilson_interval(fact_errs, n),
            "core_errs": core_errs,
            "core_err_rate": round(core_errs / n, 4),
            "core_ci": wilson_interval(core_errs, n)
        }
    return сводка
