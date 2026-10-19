# -*- coding: utf-8 -*-
"""Архитектура блока «живой_стиль» (тип вопроса + стиль живого ответа сообщества).

Принимает только токены запроса. Тематических понятий с шины не читает:
V нулевая, читает только собственное понятие для триггера синтеза.
На такте 1: работает с пустым срезом шины (изоляция).
На такте 2: счета не меняются (V=0), синтез — только стилевой шаблон.
"""
import json
import zlib
import numpy as np


def индекс(соль, токен, корзины):
    return zlib.crc32((соль + "\x1f" + токен).encode("utf-8")) % корзины


def индексы(соль, токены, корзины):
    return np.fromiter((индекс(соль, t, корзины) for t in токены), dtype=np.int64, count=len(токены))


def загрузить(путь, паспорт):
    with np.load(путь, allow_pickle=False) as z:
        P = {k: z[k] for k in z.files}
    cfg = паспорт["настройки"]
    obj = {
        "E": P["E"],
        "U": P["U"],
        "b": P["b"],
        "V": P["V"],
        "пишет": [str(x) for x in P["пишет"]],
        "читает": [str(x) for x in P["читает"]],
        "ответы": [str(x) for x in P["ответы"]],
        "соль": cfg["соль"],
        "корзины": int(cfg["корзины"]),
        "масштаб": float(cfg.get("масштаб_чтения", 1.0)),
        "_номер": {str(a): j for j, a in enumerate(P["ответы"])},
        "_кэш": (None, None),
    }
    # Шаблоны и справочные описания стилей
    if "шаблоны_json" in P:
        obj["шаблоны"] = json.loads(str(P["шаблоны_json"].item()))
    else:
        obj["шаблоны"] = {}
    return obj


def ответы(obj):
    return obj["ответы"]


def пишет(obj):
    return obj["пишет"]


def читает(obj):
    return obj["читает"]


def чисел(obj):
    return int(sum(obj[k].size for k in ("E", "U", "b", "V")))


def _h(obj, токены):
    key, h = obj["_кэш"]
    if key is токены:
        return h
    idx = индексы(obj["соль"], токены, obj["корзины"])
    if len(idx) == 0:
        h = np.zeros(obj["E"].shape[1], dtype=np.float64)
    else:
        s = obj["E"][idx].astype(np.float64).sum(0)
        h = s / np.sqrt(len(idx))
    obj["_кэш"] = (токены, h)
    return h


def проход1(obj, токены):
    # На такте 1 живой блок не пишет спекулятивных фактов до появления медицинского диагноза и правовой нормы
    return {}


def _x(obj, шина):
    R = len(obj["читает"])
    x = np.zeros(2 * R, dtype=np.float64)
    for i, k in enumerate(obj["читает"]):
        # Поддержка как точного совпадения, так и префиксов (например вывод_здоровье)
        val = None
        if k in шина:
            val = шина[k]
        else:
            for bus_k, bus_v in шина.items():
                if bus_k.startswith(k + ":"):
                    val = bus_v
                    break
        if val is not None:
            x[i] = val / obj["масштаб"]
            x[R + i] = 1.0
    return x


def проход2(obj, токены, шина):
    h = _h(obj, токены)
    s = h @ obj["U"].astype(np.float64) + obj["b"]
    if obj["читает"] and len(шина) > 0:
        x_bus = _x(obj, шина)
        s = s + x_bus @ obj["V"].astype(np.float64)
    return {a: float(v) for a, v in zip(obj["ответы"], s)}


def синтез(obj, токены, шина, ответ_id, отклики=None):
    """Синтезирует живой ответ в стиле сообщества (только стиль, без темы).

    Не читает тематические понятия шины и не подставляет названий болезней,
    статей и законов: содержание живет в блоках «здоровье»/«право».
    Использует только шаблон predicted-стиля из весов блока.
    """
    шаблоны = obj.get("шаблоны", {})
    шаблон_данные = шаблоны.get(ответ_id, {})
    заголовок = шаблон_данные.get("заголовок", "Совет сообщества:")
    шаблон_текста = шаблон_данные.get("текст", "")
    if not шаблон_текста:
        return "%s\n\nОтвечай дружелюбно и по делу, уточни детали одним вопросом." % заголовок
    try:
        текст_ответа = шаблон_текста.format(статья="—", болезнь="—", право="—")
    except (KeyError, IndexError):
        текст_ответа = шаблон_текста
    return "%s\n\n%s" % (заголовок, текст_ответа)
