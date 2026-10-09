# -*- coding: utf-8 -*-
"""Ядро v3 — обычная программа. Не нейросеть: ни одного обученного числа, текст не читает и не понимает.

Что делает:
  1. Типы: при подключении проверяет паспорт блока по типы.json (типы входа/выхода, условия, версия типов, хеш весов,
     совпадение классов блока с перечислениями типов). Не подходит — не подключает.
  2. Подключение и снятие на ходу: attach()/detach() без перезапуска; другие блоки не трогаются.
  3. Маршрут: цепочка строится по типам из паспортов — выход одного блока идёт тому блоку, чей вход (тип + условие)
     ему соответствует. Правило детерминировано; двух блоков с одинаковым входом ядро не допускает (конфликт).
  4. След: на каждый ответ пишет, какие блоки участвовали и в каком порядке (и в файл, если задан).
  5. Доступ к параметрам: список параметров блока, заморозка, дообучение только одного блока (новая версия в своей папке).
  6. Отказ: если для очередного значения нет подходящего блока — «не знаю».

Вычисления с весами делает код архитектуры блока (папка архитектуры/), ядро только вызывает его.
"""
import datetime
import importlib.util
import json
import os
import shutil

from .типы import Types, sha256_file

NOT_KNOWN = "не знаю"
MAX_STEPS = 8
REQUIRED = ("имя", "версия", "роль", "вход", "выход", "архитектура", "веса", "типы_sha256", "обучение")


class Block:
    def __init__(self, path, passport, arch, obj):
        self.path, self.passport, self.arch, self.obj = path, passport, arch, obj
        self.name = passport["имя"]
        self.sha256 = passport["веса"]["sha256"]

    @property
    def port_in(self):
        return self.passport["вход"]

    @property
    def port_out(self):
        return self.passport["выход"]


class Kernel:
    def __init__(self, types_dir, arch_dir, trace_path=None):
        self.types = Types(types_dir)
        self.arch_dir = arch_dir
        self.blocks = {}          # имя -> Block (порядок подключения не влияет на маршрут)
        self.frozen = set()
        self.trace_path = trace_path
        self._arch_cache = {}

    # ---------------- подключение ----------------
    def _arch(self, name):
        if name not in self._arch_cache:
            p = os.path.join(self.arch_dir, name + ".py")
            if not os.path.exists(p):
                raise ValueError("нет кода архитектуры %r" % name)
            spec = importlib.util.spec_from_file_location("arch_" + str(len(self._arch_cache)), p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._arch_cache[name] = mod
        return self._arch_cache[name]

    def check_passport(self, block_dir):
        """(паспорт, ошибки). Только чтение файлов, блок не подключается."""
        pp = os.path.join(block_dir, "паспорт.json")
        if not os.path.exists(pp):
            return None, ["нет паспорт.json"]
        with open(pp, encoding="utf-8") as f:
            ps = json.load(f)
        errs = ["в паспорте нет поля %r" % k for k in REQUIRED if k not in ps]
        if errs:
            return ps, errs
        errs += self.types.validate_port(ps["вход"], "вход")
        errs += self.types.validate_port(ps["выход"], "выход")
        if ps["типы_sha256"] != self.types.sha256:
            errs.append("блок обучен под другие типы (типы_sha256 не совпадает с текущим типы.json)")
        wp = os.path.join(block_dir, ps["веса"].get("файл", ""))
        if not os.path.isfile(wp):
            errs.append("нет файла весов %r" % ps["веса"].get("файл"))
        elif sha256_file(wp) != ps["веса"].get("sha256"):
            errs.append("файл весов не совпадает с паспортом (sha256)")
        if ps["выход"].get("тип") == "Ответ" and "область" not in (ps["выход"].get("условие") or {}):
            errs.append("блок с выходом Ответ должен указать условие выхода «область»")
        return ps, errs

    def attach(self, block_dir):
        """Подключить блок на ходу. Возвращает (True, имя) или (False, причины)."""
        ps, errs = self.check_passport(block_dir)
        if errs:
            return False, errs
        if ps["имя"] in self.blocks:
            return False, ["блок с именем %r уже подключён" % ps["имя"]]
        for b in self.blocks.values():
            if b.port_in.get("тип") == ps["вход"].get("тип") and \
                    (b.port_in.get("условие") or {}) == (ps["вход"].get("условие") or {}):
                return False, ["конфликт входа с блоком %r: снимите его, прежде чем подключать этот" % b.name]
        try:
            arch = self._arch(ps["архитектура"])
            obj = arch.load(os.path.join(block_dir, ps["веса"]["файл"]), ps, self.types.dir)
        except Exception as e:  # noqa: BLE001
            return False, ["архитектура не загрузила веса: %s" % e]
        errs = self._check_interface(ps, arch.interface(obj))
        if errs:
            return False, errs
        self.blocks[ps["имя"]] = Block(block_dir, ps, arch, obj)
        return True, ps["имя"]

    def _check_interface(self, ps, iface):
        """Сверка того, что реально лежит в весах, с перечислениями типов."""
        errs = []
        if "классы" in iface:
            d = (ps["выход"].get("условие") or {}).get("область")
            if d is None or list(iface["классы"]) != self.types.answers[d]:
                errs.append("классы блока не совпадают с Ответы[%s] из типов" % d)
        if "области" in iface and list(iface["области"]) != self.types.domains:
            errs.append("области блока не совпадают с перечислением Область")
        if "словарь_sha256" in iface and iface["словарь_sha256"] != self.types.spec["словарь"]["sha256"]:
            errs.append("словарь блока не совпадает со словарём типов")
        return errs

    def detach(self, name):
        if name not in self.blocks:
            return False
        del self.blocks[name]
        self.frozen.discard(name)
        return True

    def attached(self):
        return [{"имя": b.name, "версия": b.passport["версия"], "вход": b.port_in, "выход": b.port_out,
                 "sha256": b.sha256[:12], "заморожен": b.name in self.frozen} for b in sorted(self.blocks.values(), key=lambda x: x.name)]

    # ---------------- маршрут ----------------
    def _consumers(self, tname, value):
        return sorted((b for b in self.blocks.values() if Types.port_matches(b.port_in, tname, value)), key=lambda b: b.name)

    def plan(self, start="Текст"):
        """Все цепочки, которые можно построить по паспортам от типа start до конечного типа (статически)."""
        chains = []

        def walk(tname, cond, path):
            if self.types.is_terminal(tname):
                chains.append(path)
                return
            if len(path) >= MAX_STEPS:
                return
            for b in sorted(self.blocks.values(), key=lambda x: x.name):
                pin = b.port_in
                if pin["тип"] != tname or b.name in path:
                    continue
                if any(cond.get(k, v) != v for k, v in (pin.get("условие") or {}).items()):
                    continue
                walk(b.port_out["тип"], dict(b.port_out.get("условие") or {}), path + [b.name])

        walk(start, {}, [])
        return chains

    def ask(self, text, full=False):
        """Ответ на запрос и след. Ответ — значение типа Ответ или строка «не знаю»."""
        return self.ask_typed("Текст", text, full)

    def ask_typed(self, tname, value, full=False):
        """Запрос, поданный значением любого типа (например готовым Разбором). full — класть в след полные значения."""
        text, trace = value if tname == "Текст" else "<%s>" % tname, []
        errs = self.types.validate(tname, value)
        if errs:
            return self._finish(text, NOT_KNOWN, trace, "запрос не типа %s: %s" % (tname, errs))
        for _ in range(MAX_STEPS):
            if self.types.is_terminal(tname):
                return self._finish(text, value, trace, None)
            cands = self._consumers(tname, value)
            if not cands:
                return self._finish(text, NOT_KNOWN, trace, "нет блока для %s%s" % (tname, _cond_str(value)))
            if len(cands) > 1:  # attach() такого не допускает; на всякий случай — отказ, а не выбор наугад
                return self._finish(text, NOT_KNOWN, trace, "неоднозначно: %s" % [b.name for b in cands])
            b = cands[0]
            out = b.arch.run(b.obj, value)
            otype = b.port_out["тип"]
            errs = self.types.validate(otype, out)
            if not errs and not Types.port_matches(b.port_out, otype, out):
                errs = ["выход не соответствует условию выхода из паспорта"]
            trace.append({"блок": b.name, "версия": b.passport["версия"], "sha256": b.sha256[:12],
                          "вход": tname + _cond_str(value), "выход": otype + _cond_str(out), "кратко": _brief(otype, out)})
            if full:
                trace[-1]["значение"] = out
            if errs:
                return self._finish(text, NOT_KNOWN, trace, "блок %s нарушил тип %s: %s" % (b.name, otype, errs))
            tname, value = otype, out
        return self._finish(text, NOT_KNOWN, trace, "цепочка длиннее %d шагов" % MAX_STEPS)

    def _finish(self, text, answer, trace, reason):
        rec = {"вопрос": text, "ответ": answer if answer == NOT_KNOWN else {"область": answer["область"], "id": answer["id"], "p": answer["p"]},
               "путь": [s["блок"] for s in trace], "шаги": trace}
        if reason:
            rec["отказ"] = reason
        if self.trace_path:
            with open(self.trace_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return answer, rec

    # ---------------- параметры ----------------
    def params(self, name):
        b = self.blocks[name]
        p = b.arch.params(b.obj)
        rows = [{"параметр": k, "форма": list(v.shape), "чисел": int(v.size)} for k, v in p.items()]
        return {"блок": name, "параметры": rows, "всего_чисел": sum(r["чисел"] for r in rows), "заморожен": name in self.frozen}

    def param_values(self, name):
        b = self.blocks[name]
        return b.arch.params(b.obj)

    def freeze(self, name):
        if name not in self.blocks:
            raise KeyError(name)
        self.frozen.add(name)

    def unfreeze(self, name):
        self.frozen.discard(name)

    def finetune(self, name, data, settings=None, out_root=None):
        """Дообучить ОДИН блок. data — [(значение типа входа блока, правильный выход)].
        Каждое значение проверяется по типу входа. Результат — новая версия блока в своей папке, подключается вместо старой.
        Файлы других блоков не открываются на запись."""
        if name in self.frozen:
            raise PermissionError("блок %r заморожен" % name)
        b = self.blocks[name]
        for x, _ in data:
            errs = self.types.validate(b.port_in["тип"], x)
            if errs or not Types.port_matches(b.port_in, b.port_in["тип"], x):
                raise ValueError("данные дообучения не типа входа блока: %s" % (errs or "условие"))
        new_params, log = b.arch.finetune(b.obj, data, settings or {})
        ver = int(b.passport["версия"]) + 1
        out_dir = os.path.join(out_root or os.path.dirname(b.path), "%s@%d" % (name, ver))
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.makedirs(out_dir)
        wfile = os.path.join(out_dir, b.passport["веса"]["файл"])
        b.arch.save(new_params, b.obj, wfile)
        ps = json.loads(json.dumps(b.passport))
        ps["версия"] = ver
        ps["веса"]["sha256"] = sha256_file(wfile)
        ps["родитель"] = {"версия": b.passport["версия"], "sha256": b.sha256}
        ps["дообучение"] = {"когда": datetime.datetime.now().isoformat(timespec="seconds"), "строк": len(data),
                            "настройки": settings or {}, "журнал": log}
        with open(os.path.join(out_dir, "паспорт.json"), "w", encoding="utf-8") as f:
            json.dump(ps, f, ensure_ascii=False, indent=1)
        self.detach(name)
        ok, msg = self.attach(out_dir)
        if not ok:
            raise RuntimeError("новая версия не подключилась: %s" % msg)
        return out_dir


def _cond_str(v):
    return "[область=%s]" % v["область"] if isinstance(v, dict) and "область" in v else ""


def _brief(tname, v):
    if tname == "Разбор":
        return {"область": v["область"], "p": round(v["p_область"][v["область"]], 4), "основ": len(v["основы"]),
                "замены": v.get("замены", [])}
    if tname == "Ответ":
        return {"id": v["id"], "p": round(v["p"], 4)}
    return None
