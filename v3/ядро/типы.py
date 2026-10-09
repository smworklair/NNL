# -*- coding: utf-8 -*-
"""Типы ядра: загрузка типы.json + словарь.txt и проверка значений и паспортов. Обучаемых чисел здесь нет."""
import hashlib
import json
import os


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Types:
    def __init__(self, types_dir):
        self.dir = types_dir
        self.path = os.path.join(types_dir, "типы.json")
        with open(self.path, encoding="utf-8") as f:
            self.spec = json.load(f)
        self.sha256 = sha256_file(self.path)
        vpath = os.path.join(types_dir, self.spec["словарь"]["файл"])
        if sha256_file(vpath) != self.spec["словарь"]["sha256"]:
            raise RuntimeError("словарь.txt не совпадает с типы.json (sha256) — типы испорчены")
        with open(vpath, encoding="utf-8") as f:
            self.vocab = [l.rstrip("\n") for l in f if l.strip()]
        self.vocab_set = frozenset(self.vocab)
        self.domains = list(self.spec["перечисления"]["Область"])
        self.answers = {d: list(ids) for d, ids in self.spec["перечисления"]["Ответы"].items()}
        self._answer_sets = {d: frozenset(ids) for d, ids in self.answers.items()}
        self.names = set(self.spec["типы"])

    def is_terminal(self, tname):
        return bool(self.spec["типы"].get(tname, {}).get("конечный"))

    # ---------- проверка значений ----------
    def validate(self, tname, v):
        """Список ошибок (пустой — значение соответствует типу)."""
        if tname not in self.names:
            return ["неизвестный тип %r" % tname]
        if tname == "Текст":
            return [] if isinstance(v, str) else ["Текст должен быть строкой"]
        if not isinstance(v, dict):
            return ["%s должен быть записью" % tname]
        errs = []
        if tname == "Разбор":
            if v.get("область") not in self.domains:
                errs.append("область %r не из перечисления Область" % v.get("область"))
            p = v.get("p_область")
            if not isinstance(p, dict) or set(p) - set(self.domains) or not all(_prob(x) for x in p.values()):
                errs.append("p_область: ключи из Область, значения в [0,1]")
            st = v.get("основы")
            if not isinstance(st, list):
                errs.append("основы должны быть списком")
            else:
                bad = [s for s in st if s not in self.vocab_set]
                if bad:
                    errs.append("основы вне словаря типа: %s" % bad[:5])
            for z in v.get("замены", []):
                if not (isinstance(z, list) and len(z) == 3 and z[1] in self.vocab_set and _prob(z[2])):
                    errs.append("замены: элемент [слово, основа из словаря, p]")
                    break
            extra = set(v) - {"область", "p_область", "основы", "замены"}
            if extra:
                errs.append("лишние поля Разбора: %s" % sorted(extra))
            return errs
        if tname == "Ответ":
            d = v.get("область")
            if d not in self.domains:
                return ["область %r не из перечисления Область" % d]
            if v.get("id") not in self._answer_sets[d]:
                errs.append("id %r не из Ответы[%s]" % (v.get("id"), d))
            if not _prob(v.get("p")):
                errs.append("p должно быть в [0,1]")
            for c in v.get("кандидаты", []):
                if not (isinstance(c, list) and len(c) == 2 and c[0] in self._answer_sets[d] and _prob(c[1])):
                    errs.append("кандидаты: элемент [id из Ответы[%s], p]" % d)
                    break
            extra = set(v) - {"область", "id", "p", "кандидаты"}
            if extra:
                errs.append("лишние поля Ответа: %s" % sorted(extra))
            return errs
        return ["нет правила проверки для типа %r" % tname]

    # ---------- порты паспортов ----------
    def validate_port(self, port, side):
        """port = {"тип": ..., "условие": {поле: значение}}; условие — только на поля-перечисления."""
        errs = []
        t = port.get("тип")
        if t not in self.names:
            return ["%s: неизвестный тип %r" % (side, t)]
        for field, val in (port.get("условие") or {}).items():
            fspec = self.spec["типы"][t].get("поля", {}).get(field)
            if not fspec or fspec.get("вид") != "перечисление" or fspec.get("из") != "Область":
                errs.append("%s: условие на поле %r, которое не перечисление Область" % (side, field))
            elif val not in self.domains:
                errs.append("%s: значение условия %r не из Область" % (side, val))
        return errs

    @staticmethod
    def port_matches(port, tname, value):
        if port.get("тип") != tname:
            return False
        for field, val in (port.get("условие") or {}).items():
            if not isinstance(value, dict) or value.get(field) != val:
                return False
        return True


def _prob(x):
    return isinstance(x, (int, float)) and 0.0 <= float(x) <= 1.0
