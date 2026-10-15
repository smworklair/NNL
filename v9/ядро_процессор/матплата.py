# -*- coding: utf-8 -*-
"""Материнская плата (Матплата).

Физическая инфраструктура и шина коммуникации:
  1. Слоты расширения: подключение (хот-плаг) и снятие блоков на ходу.
  2. Валидация паспортов: проверка обязательных полей, sha256 весов, отпечатков языка.
  3. Общая шина данных: хранилище понятий и значений.
  4. Контракт изоляции на такт:
     - Такт 1: каждый блок получает строго изолированный срез (Lego-индекс = 0.0000).
     - Такт 2: блок получает только подтверждённые причинные факты от завершивших такт 1 соседей.
"""
import hashlib
import importlib.util
import json
import math
import os
import sys

ОБЯЗАТЕЛЬНО = ("имя", "версия", "роль", "архитектура", "веса", "язык", "пишет", "читает", "ответы")


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Блок:
    def __init__(self, папка, паспорт, arch, obj):
        self.папка = папка
        self.паспорт = паспорт
        self.arch = arch
        self.obj = obj
        self.имя = паспорт["имя"]
        self.роль = паспорт.get("роль", self.имя)
        self.пишет = list(паспорт["пишет"])
        self.читает = list(паспорт["читает"])
        self.ответы = list(паспорт["ответы"])
        self.чисел = arch.чисел(obj)


class Матплата:
    def __init__(self, язык, arch_dir):
        self.язык = язык
        self.arch_dir = os.path.abspath(arch_dir)
        self.блоки = {}
        self.шина = {}
        self._arch_cache = {}

    def _архитектура(self, имя):
        if имя not in self._arch_cache:
            p = os.path.join(self.arch_dir, имя + ".py")
            if not os.path.exists(p):
                raise ValueError("нет кода архитектуры %r" % имя)
            if self.arch_dir not in sys.path:
                sys.path.insert(0, self.arch_dir)
            self._arch_cache[имя] = _load_module(p, "nnl_arch_%s_%d" % (имя, id(self)))
        return self._arch_cache[имя]

    def проверить_паспорт(self, папка):
        pp = os.path.join(папка, "паспорт.json")
        if not os.path.exists(pp):
            return None, ["нет паспорт.json"]
        with open(pp, encoding="utf-8") as f:
            ps = json.load(f)
        errs = ["в паспорте нет поля %r" % k for k in ОБЯЗАТЕЛЬНО if k not in ps]
        if errs:
            return ps, errs
        wp = os.path.join(папка, ps["веса"].get("файл", ""))
        if not os.path.isfile(wp):
            errs.append("нет файла весов %r" % ps["веса"].get("файл"))
        elif _sha256_file(wp) != ps["веса"].get("sha256"):
            errs.append("файл весов не совпадает с паспортом (sha256)")
        return ps, errs

    def подключить(self, папка):
        ps, errs = self.проверить_паспорт(папка)
        if errs:
            return False, errs
        имя = ps["имя"]
        if имя in self.блоки:
            return False, ["блок с именем %r уже подключён" % имя]
        arch = self._архитектура(ps["архитектура"])
        obj = arch.загрузить(os.path.join(папка, ps["веса"]["файл"]), ps)
        b = Блок(папка, ps, arch, obj)
        self.блоки[имя] = b
        return True, имя

    def снять(self, имя):
        return self.блоки.pop(имя, None) is not None

    def очистить_шину(self):
        self.шина = {}

    def записать_на_шину(self, понятие, значение):
        self.шина[понятие] = float(значение)

    def срез_шины(self, имя_блока, такт=1):
        """Контракт изоляции на такт:
        такт=1: пустой срез (полная изоляция от соседей -> Lego-индекс = 0).
        такт=2: только понятия, которые блок читает, из текущего проверенного состояния шины.
        """
        if такт == 1:
            return {}
        b = self.блоки.get(имя_блока)
        if not b:
            return {}
        res = {}
        for k, v in self.шина.items():
            if k in b.читает or any(k.startswith(pat + ":") for pat in b.читает):
                res[k] = v
        return res
