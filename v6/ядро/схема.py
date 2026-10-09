# -*- coding: utf-8 -*-
"""Наборы типов по схеме. В коде нет ни одного предметного правила: всё, что проверяется, записано в файле набора.

Набор типов — папка типы/<имя>/ с файлом набор.json:
  {"набор": "общие", "версия": 1,
   "перечисления": {"Имя": [..] | {"ключ": [..]} | {"файл": "словарь.txt", "sha256": ".."}},
   "типы": {"Имя": <схема>, ...}}
Схема значения (поле «вид»):
  строка | число {от, до} | целое {от, до} | логическое
  перечисление {"из": имя перечисления, "по_полю": поле записи (если перечисление — словарь списков)} | {"значения": [..]}
  список {"элемент": <схема>, "мин", "макс"}
  кортеж {"элементы": [<схема>, ...]}
  запись {"поля": {имя: <схема> (+ "необязательно": true)}}
  вероятности {"ключи": имя перечисления}   — словарь ключ → число в [0,1]
У типа верхнего уровня могут быть флаги: "запрос": true (вход от человека), "конечный": true (ответ человеку).
Проверки, которые схемой не выразить (например арифметика в решении), набор кладёт в проверки.py: функции
проверить_<Тип>(значение) -> список замечаний. Это код набора типов, не ядра.
"""
import hashlib
import importlib.util
import json
import os


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TypeSet:
    def __init__(self, folder):
        self.dir = folder
        self.path = os.path.join(folder, "набор.json")
        with open(self.path, encoding="utf-8") as f:
            self.spec = json.load(f)
        self.name = self.spec["набор"]
        self.sha256 = sha256_file(self.path)
        self.enums = {}
        for en, ev in self.spec.get("перечисления", {}).items():
            if isinstance(ev, dict) and "файл" in ev:
                p = os.path.join(folder, ev["файл"])
                if sha256_file(p) != ev["sha256"]:
                    raise RuntimeError("набор %s: файл %s не совпадает по sha256" % (self.name, ev["файл"]))
                with open(p, encoding="utf-8") as f:
                    self.enums[en] = frozenset(l.rstrip("\n") for l in f if l.strip())
            elif isinstance(ev, dict):
                self.enums[en] = {k: frozenset(v) for k, v in ev.items()}
            else:
                self.enums[en] = frozenset(ev)
        self.types = self.spec["типы"]
        self.checks = None
        cp = os.path.join(folder, "проверки.py")
        if os.path.exists(cp):
            spec = importlib.util.spec_from_file_location("checks_" + self.name, cp)
            self.checks = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.checks)

    def has(self, tname):
        return tname in self.types

    def flag(self, tname, flag):
        return bool(self.types.get(tname, {}).get(flag))

    def enum_values(self, en):
        """Значения перечисления (для простого — множество, для словаря — словарь множеств)."""
        return self.enums.get(en)

    # ---------- проверка значения ----------
    def validate(self, tname, value):
        if tname not in self.types:
            return ["в наборе %s нет типа %r" % (self.name, tname)]
        errs = []
        self._check(self.types[tname], value, tname, [], errs)
        if not errs and self.checks is not None and hasattr(self.checks, "проверить_" + tname):
            errs += ["проверка набора: %s" % e for e in getattr(self.checks, "проверить_" + tname)(value)]
        return errs

    def _check(self, s, v, path, records, errs):
        kind = s.get("вид")
        if kind == "строка":
            if not isinstance(v, str):
                errs.append("%s: ждали строку" % path)
        elif kind in ("число", "целое"):
            ok = isinstance(v, (int, float)) and not isinstance(v, bool)
            if kind == "целое":
                ok = ok and float(v).is_integer()
            if not ok:
                errs.append("%s: ждали %s" % (path, kind))
            elif ("от" in s and v < s["от"]) or ("до" in s and v > s["до"]):
                errs.append("%s: %r вне [%s, %s]" % (path, v, s.get("от"), s.get("до")))
        elif kind == "логическое":
            if not isinstance(v, bool):
                errs.append("%s: ждали да/нет" % path)
        elif kind == "перечисление":
            allowed = self._allowed(s, records)
            if allowed is None:
                errs.append("%s: не найдено перечисление %r" % (path, s.get("из")))
            elif not isinstance(v, str) or v not in allowed:
                errs.append("%s: %r не из перечисления %s" % (path, v, s.get("из") or s.get("значения")))
        elif kind == "список":
            if not isinstance(v, list):
                errs.append("%s: ждали список" % path)
                return
            if len(v) < s.get("мин", 0) or ("макс" in s and len(v) > s["макс"]):
                errs.append("%s: длина %d вне границ" % (path, len(v)))
            for i, x in enumerate(v):
                self._check(s["элемент"], x, "%s[%d]" % (path, i), records, errs)
                if len(errs) > 5:
                    return
        elif kind == "кортеж":
            el = s["элементы"]
            if not isinstance(v, list) or len(v) != len(el):
                errs.append("%s: ждали кортеж из %d" % (path, len(el)))
                return
            for i, (es, x) in enumerate(zip(el, v)):
                self._check(es, x, "%s[%d]" % (path, i), records, errs)
        elif kind == "запись":
            if not isinstance(v, dict):
                errs.append("%s: ждали запись" % path)
                return
            fields = s.get("поля", {})
            extra = set(v) - set(fields)
            if extra:
                errs.append("%s: лишние поля %s" % (path, sorted(extra)))
            for fn, fs in fields.items():
                if fn not in v:
                    if not fs.get("необязательно"):
                        errs.append("%s: нет поля %r" % (path, fn))
                    continue
                self._check(fs, v[fn], "%s.%s" % (path, fn), records + [v], errs)
        elif kind == "вероятности":
            keys = self.enums.get(s.get("ключи"))
            if not isinstance(v, dict) or keys is None or set(v) - set(keys) or \
                    not all(isinstance(x, (int, float)) and 0.0 <= x <= 1.0 for x in v.values()):
                errs.append("%s: ждали вероятности по %s" % (path, s.get("ключи")))
        else:
            errs.append("%s: неизвестный вид схемы %r" % (path, kind))

    def _allowed(self, s, records):
        if "значения" in s:
            return frozenset(s["значения"])
        e = self.enums.get(s.get("из"))
        if e is None:
            return None
        if isinstance(e, dict):
            key_field = s.get("по_полю")
            for rec in reversed(records):
                if key_field in rec:
                    return e.get(rec[key_field], frozenset())
            return None
        return e

    def fingerprint(self, tname):
        """Отпечаток ОДНОГО типа: его схема + перечисления, на которые он ссылается, + проверка набора для него.
        Блок помнит отпечатки своих типов, поэтому новые типы в наборе старые блоки не ломают."""
        names, stack = set(), [self.types[tname]]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                for k in ("из", "ключи"):
                    if isinstance(x.get(k), str):
                        names.add(x[k])
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
        enums = {}
        for en in sorted(names):
            ev = self.spec.get("перечисления", {}).get(en)
            enums[en] = ev if not (isinstance(ev, dict) and "файл" in ev) else {"sha256": ev["sha256"]}
        blob = {"тип": self.types[tname], "перечисления": enums}
        if self.checks is not None and hasattr(self.checks, "проверить_" + tname):
            blob["проверки_sha256"] = sha256_file(os.path.join(self.dir, "проверки.py"))
        return hashlib.sha256(json.dumps(blob, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def enum_fields(self, tname):
        """Поля-перечисления верхнего уровня типа (на них можно ставить условие входа)."""
        out = {}
        for fn, fs in self.types.get(tname, {}).get("поля", {}).items():
            if fs.get("вид") == "перечисление":
                out[fn] = fs
        return out


class Types:
    """Все наборы типов из папки типы/. Имя типа — «набор:Тип»."""

    def __init__(self, root):
        self.root = root
        self.sets = {}
        for d in sorted(os.listdir(root)):
            if os.path.isfile(os.path.join(root, d, "набор.json")):
                ts = TypeSet(os.path.join(root, d))
                self.sets[ts.name] = ts

    def split(self, full):
        if not isinstance(full, str) or ":" not in full:
            return None, None
        s, t = full.split(":", 1)
        ts = self.sets.get(s)
        return (ts, t) if ts is not None and ts.has(t) else (None, None)

    def exists(self, full):
        return self.split(full)[0] is not None

    def validate(self, full, value):
        ts, t = self.split(full)
        if ts is None:
            return ["неизвестный тип %r" % full]
        return ts.validate(t, value)

    def flag(self, full, flag):
        ts, t = self.split(full)
        return ts is not None and ts.flag(t, flag)

    def fingerprint(self, full):
        ts, t = self.split(full)
        return ts.fingerprint(t) if ts is not None else None

    def validate_port(self, port, side):
        errs = []
        full = port.get("тип")
        ts, t = self.split(full)
        if ts is None:
            return ["%s: неизвестный тип %r" % (side, full)]
        ef = ts.enum_fields(t)
        fields = ts.types[t].get("поля", {})
        for field, val in (port.get("условие") or {}).items():
            if fields.get(field, {}).get("вид") == "строка" and isinstance(val, str):
                continue   # условие на строковое поле — простое равенство
            if field not in ef:
                errs.append("%s: условие на поле %r, которое не перечисление и не строка" % (side, field))
                continue
            allowed = ts._allowed(ef[field], [])
            if allowed is None or val not in allowed:
                errs.append("%s: значение условия %r не из перечисления" % (side, val))
        return errs

    @staticmethod
    def port_matches(port, full, value):
        if port.get("тип") != full:
            return False
        for field, val in (port.get("условие") or {}).items():
            if not isinstance(value, dict) or value.get(field) != val:
                return False
        return True
