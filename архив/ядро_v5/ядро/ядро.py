# -*- coding: utf-8 -*-
"""Ядро v4 — обычная программа, одна на все задачи. Ни одного обученного числа, текст не читает и не понимает.

Что умеет:
  1. Типы: любые наборы типов из папки типы/ (схема в файле, ядро не знает ни одной предметной области).
     При подключении проверяет паспорт: типы входа/выхода, версии наборов типов, хеш весов, совпадение классов
     блока с объявленными, бюджет чисел. Не подходит — не подключает.
  2. Подключение и снятие на ходу, без перезапуска и без переобучения других блоков.
  3. Маршрут (детерминированный):
     а) запрос человека получают «входные» блоки (вход — тип с флагом «запрос»);
        один входной блок — ему; несколько — каждый подаёт заявку p ∈ [0,1] («насколько вопрос мой»),
        ядро берёт наибольшую не ниже порога, при равенстве — по имени; ниже порога у всех — «не знаю»;
     б) дальше цепочка по типам: выход блока идёт тому блоку, чей вход (тип + условие) ему подходит.
  4. След: заявки, шаги цепочки (блок, версия, хеш весов), отказ с причиной; по желанию — в файл.
  5. Параметры: список, заморозка, дообучение одного блока в новую версию (старая не трогается).
  6. Отказ «не знаю», если подходящего блока нет.
  7. Контроль: у блока в паспорте может быть свой контрольный набор; ядро прогоняет контроль всех блоков
     и показывает, изменила ли вставка/снятие блока ответы других блоков.
Вычисления с весами делает код архитектуры блока (папка архитектуры/), ядро только вызывает его.
"""
import datetime
import importlib.util
import json
import os
import shutil

from .схема import Types, sha256_file

NOT_KNOWN = "не знаю"
MAX_STEPS = 8
CLAIM_THRESHOLD = 0.5
REQUIRED = ("имя", "версия", "роль", "вход", "выход", "архитектура", "веса", "типы", "обучение")


class Block:
    def __init__(self, path, passport, arch, obj):
        self.path, self.passport, self.arch, self.obj = path, passport, arch, obj
        self.name = passport["имя"]
        self.sha256 = passport["веса"]["sha256"]
        self.answers = frozenset(passport["ответы"]) if isinstance(passport.get("ответы"), list) else None

    @property
    def port_in(self):
        return self.passport["вход"]

    @property
    def port_out(self):
        return self.passport["выход"]

    @property
    def numbers(self):
        return int(self.passport["веса"].get("чисел", 0))


class Kernel:
    def __init__(self, types_root, arch_dir, trace_path=None, budget=None, claim_threshold=CLAIM_THRESHOLD, dispute=False):
        self.types = Types(types_root)
        self.arch_dir = arch_dir
        self.blocks = {}
        self.frozen = set()
        self.trace_path = trace_path
        self.budget = budget
        self.claim_threshold = claim_threshold
        self.dispute = dispute     # спор заявок: несколько заявок ≥ порога → спросить знания всех, взять самый уверенный ответ
        self._arch_cache = {}

    # ================= подключение =================
    def _arch(self, name):
        if name not in self._arch_cache:
            p = os.path.join(self.arch_dir, name + ".py")
            if not os.path.exists(p):
                raise ValueError("нет кода архитектуры %r" % name)
            spec = importlib.util.spec_from_file_location("arch_%d" % len(self._arch_cache), p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._arch_cache[name] = mod
        return self._arch_cache[name]

    def _is_entry(self, port):
        return self.types.flag(port.get("тип"), "запрос")

    def check_passport(self, block_dir):
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
        used_types = sorted({ps["вход"].get("тип", ""), ps["выход"].get("тип", "")})
        if any(":" in k for k in ps["типы"]):          # отпечатки отдельных типов (v4)
            for full in used_types:
                if self.types.exists(full) and ps["типы"].get(full) != self.types.fingerprint(full):
                    errs.append("блок обучен под другую версию типа %r (отпечаток не совпадает)" % full)
        else:                                          # отпечаток всего набора (блоки v3)
            for s in sorted({t.split(":")[0] for t in used_types}):
                ts = self.types.sets.get(s)
                if ts is not None and ps["типы"].get(s) != ts.sha256:
                    errs.append("блок обучен под другую версию набора типов %r (sha256 не совпадает)" % s)
        wp = os.path.join(block_dir, ps["веса"].get("файл", ""))
        if not os.path.isfile(wp):
            errs.append("нет файла весов %r" % ps["веса"].get("файл"))
        elif sha256_file(wp) != ps["веса"].get("sha256"):
            errs.append("файл весов не совпадает с паспортом (sha256)")
        if "ответы" in ps and not (isinstance(ps["ответы"], list) and all(isinstance(x, str) for x in ps["ответы"])):
            errs.append("поле «ответы» — список строк")
        return ps, errs

    def attach(self, block_dir):
        """Подключить блок на ходу. (True, имя) или (False, [причины])."""
        ps, errs = self.check_passport(block_dir)
        if errs:
            return False, errs
        if ps["имя"] in self.blocks:
            return False, ["блок с именем %r уже подключён" % ps["имя"]]
        entry = self._is_entry(ps["вход"])
        for b in self.blocks.values():
            same = b.port_in.get("тип") == ps["вход"].get("тип") and \
                (b.port_in.get("условие") or {}) == (ps["вход"].get("условие") or {})
            if same and not entry:
                return False, ["конфликт входа с блоком %r: снимите его, прежде чем подключать этот" % b.name]
        if entry:
            entries = [b for b in self.blocks.values() if self._is_entry(b.port_in)]
            if entries and (not ps.get("заявка") or any(not b.passport.get("заявка") for b in entries)):
                names = [b.name for b in entries] + [ps["имя"]]
                return False, ["несколько входных блоков %s — каждый должен уметь подавать заявку (поле «заявка»)" % names]
        if self.budget is not None and self.total_numbers() + int(ps["веса"].get("чисел", 0)) > self.budget:
            return False, ["превышен бюджет чисел: %d + %d > %d" % (self.total_numbers(), int(ps["веса"].get("чисел", 0)), self.budget)]
        try:
            arch = self._arch(ps["архитектура"])
            obj = arch.load(os.path.join(block_dir, ps["веса"]["файл"]), ps, self._types_dir_for(ps))
        except Exception as e:  # noqa: BLE001
            return False, ["архитектура не загрузила веса: %s" % e]
        if ps.get("заявка") and not hasattr(arch, "claim"):
            return False, ["в паспорте «заявка», а у архитектуры нет функции claim"]
        errs = self._check_interface(ps, arch, obj)
        if errs:
            return False, errs
        self.blocks[ps["имя"]] = Block(block_dir, ps, arch, obj)
        return True, ps["имя"]

    def _types_dir_for(self, ps):
        """Папка набора типов, нужная коду архитектуры (набор выхода, иначе входа)."""
        for side in ("выход", "вход"):
            ts, _ = self.types.split(ps[side].get("тип"))
            if ts is not None and ts.name != "общие":
                return ts.dir
        ts, _ = self.types.split(ps["выход"].get("тип"))
        return ts.dir if ts is not None else self.types.root

    def _check_interface(self, ps, arch, obj):
        """Сверка того, что реально лежит в весах, с типами и паспортом."""
        errs = []
        iface = arch.interface(obj)
        n_real = sum(int(v.size) for v in arch.params(obj).values())
        if n_real != int(ps["веса"].get("чисел", -1)):
            errs.append("в весах %d чисел, а в паспорте %s" % (n_real, ps["веса"].get("чисел")))
        if "классы" in iface:
            classes = list(iface["классы"])
            ts, t = self.types.split(ps["выход"]["тип"])
            idspec = ts.types[t].get("поля", {}).get("id", {}) if ts else {}
            if idspec.get("вид") == "перечисление":
                allowed = ts._allowed(idspec, [ps["выход"].get("условие") or {}])
                if allowed is None or set(classes) != set(allowed) or len(classes) != len(allowed):
                    errs.append("классы блока не совпадают с перечислением типа выхода")
            if isinstance(ps.get("ответы"), list) and classes != ps["ответы"]:
                errs.append("классы блока не совпадают с полем «ответы» паспорта")
        for en, vals in iface.get("перечисления", {}).items():
            found = False
            for side in ("вход", "выход"):
                ts, _ = self.types.split(ps[side].get("тип"))
                if ts is not None and en in ts.enums:
                    found = True
                    e = ts.enums[en]
                    if isinstance(e, dict) or set(vals) != set(e):
                        errs.append("перечисление %r у блока не совпадает с типами" % en)
            if not found:
                errs.append("перечисление %r блока не найдено в его типах" % en)
        for fname, sha in iface.get("файлы", {}).items():
            ok = any(ts is not None and isinstance(ts.spec.get("перечисления"), dict) and
                     any(isinstance(ev, dict) and ev.get("файл") == fname and ev.get("sha256") == sha
                         for ev in ts.spec["перечисления"].values())
                     for ts in (self.types.split(ps[s].get("тип"))[0] for s in ("вход", "выход")))
            if not ok:
                errs.append("файл %r блока не совпадает с файлом типов" % fname)
        return errs

    def detach(self, name):
        if name not in self.blocks:
            return False
        del self.blocks[name]
        self.frozen.discard(name)
        return True

    def total_numbers(self):
        return sum(b.numbers for b in self.blocks.values())

    def attached(self):
        return [{"имя": b.name, "версия": b.passport["версия"], "вход": b.port_in, "выход": b.port_out,
                 "заявка": bool(b.passport.get("заявка")), "чисел": b.numbers, "sha256": b.sha256[:12],
                 "заморожен": b.name in self.frozen} for b in sorted(self.blocks.values(), key=lambda x: x.name)]

    def summary(self):
        return {"блоков": len(self.blocks), "чисел": self.total_numbers(), "бюджет": self.budget,
                "порог_заявки": self.claim_threshold, "блоки": self.attached(), "цепочки": self.plan()}

    # ================= маршрут =================
    def _entries(self):
        return sorted((b for b in self.blocks.values() if self._is_entry(b.port_in)), key=lambda b: b.name)

    def _consumers(self, full, value):
        return sorted((b for b in self.blocks.values()
                       if not self._is_entry(b.port_in) and Types.port_matches(b.port_in, full, value)), key=lambda b: b.name)

    def plan(self):
        """Все цепочки, которые можно построить по паспортам (статически)."""
        chains = []

        def walk(full, cond, path):
            if self.types.flag(full, "конечный"):
                chains.append(path)
                return
            if len(path) >= MAX_STEPS:
                return
            for b in sorted(self.blocks.values(), key=lambda x: x.name):
                pin = b.port_in
                if self._is_entry(pin) or pin["тип"] != full or b.name in path:
                    continue
                if any(cond.get(k, v) != v for k, v in (pin.get("условие") or {}).items()):
                    continue
                walk(b.port_out["тип"], dict(b.port_out.get("условие") or {}), path + [b.name])

        for e in self._entries():
            walk(e.port_out["тип"], dict(e.port_out.get("условие") or {}), [e.name])
        return chains

    def ask(self, text, full=False):
        """Ответ на запрос человека и след. Ответ — значение конечного типа или «не знаю»."""
        trace, claims = [], []
        entries = [b for b in self._entries() if not self.types.validate(b.port_in["тип"], text)]
        if not entries:
            return self._finish(text, NOT_KNOWN, trace, claims, "нет входного блока")
        if len(entries) == 1 and not entries[0].passport.get("заявка"):
            chosen = entries[0]   # единственный входной блок без заявки (как разбор в v3) получает всё
        else:
            for b in entries:
                p = b.arch.claim(b.obj, text)
                if not isinstance(p, (int, float)) or not 0.0 <= float(p) <= 1.0:
                    return self._finish(text, NOT_KNOWN, trace, claims, "блок %s подал заявку не в [0,1]" % b.name)
                claims.append([b.name, float(p)])
            ranked = sorted(claims, key=lambda c: (-c[1], c[0]))   # наибольшая заявка, при равенстве — первое имя
            best = ranked[0]
            if best[1] < self.claim_threshold:
                return self._finish(text, NOT_KNOWN, trace, claims, "ни один блок не взял запрос (все заявки < %.2f)" % self.claim_threshold)
            contenders = [c for c in ranked if c[1] >= self.claim_threshold]
            if self.dispute and len(contenders) > 1:
                return self._dispute(contenders, text, claims, full)
            chosen = self.blocks[best[0]]
        return self._run_chain(chosen, chosen.port_in["тип"], text, text, trace, claims, full)

    def _dispute(self, contenders, text, claims, full):
        """Спор заявок: каждая область, чья заявка ≥ порога, отвечает; берётся ответ с наибольшей уверенностью p
        своего знания (при равенстве — большая заявка, затем имя). Детерминировано, без обучения."""
        results = []
        for name, cl in contenders:
            b = self.blocks[name]
            ans, tr, reason = self._walk(b, b.port_in["тип"], text, full)
            p = ans.get("p") if isinstance(ans, dict) else None
            results.append((name, cl, ans, tr, reason, p))
        ok = [r for r in results if r[2] != NOT_KNOWN and isinstance(r[5], (int, float))]
        record = [[r[0], round(r[1], 6), None if r[5] is None else round(float(r[5]), 6)] for r in results]
        if not ok:
            r = results[0]
            rec_ans, rec = self._finish(text, NOT_KNOWN, r[3], claims, "спор: ни одно знание не ответило (%s)" % r[4])
            rec["спор"] = record
            return rec_ans, rec
        win = sorted(ok, key=lambda r: (-r[5], -r[1], r[0]))[0]
        ans, rec = self._finish(text, win[2], win[3], claims, None)
        rec["спор"] = record
        return ans, rec

    def ask_typed(self, full_type, value, full=False):
        """Запрос, поданный готовым значением любого типа (для разбора причин)."""
        errs = self.types.validate(full_type, value)
        if errs:
            return self._finish("<%s>" % full_type, NOT_KNOWN, [], [], "значение не типа %s: %s" % (full_type, errs))
        cands = self._consumers(full_type, value)
        if len(cands) != 1:
            return self._finish("<%s>" % full_type, NOT_KNOWN, [], [], "нет единственного блока для %s" % full_type)
        return self._run_chain(cands[0], full_type, value, "<%s>" % full_type, [], [], full)

    def _run_chain(self, b, tname, value, text, trace, claims, full):
        ans, tr, reason = self._walk(b, tname, value, full)
        return self._finish(text, ans, trace + tr, claims, reason)

    def _walk(self, b, tname, value, full):
        """Пройти цепочку от блока b. Возвращает (ответ или «не знаю», шаги, причина отказа)."""
        trace = []
        for _ in range(MAX_STEPS):
            out = b.arch.run(b.obj, value)
            otype = b.port_out["тип"]
            errs = self.types.validate(otype, out)
            if not errs and not Types.port_matches(b.port_out, otype, out):
                errs = ["выход не соответствует условию выхода из паспорта"]
            if not errs and b.answers is not None and isinstance(out, dict) and "id" in out and out["id"] not in b.answers:
                errs = ["id %r не из списка ответов блока" % out.get("id")]
            step = {"блок": b.name, "версия": b.passport["версия"], "sha256": b.sha256[:12],
                    "вход": tname + _cond_str(value), "выход": otype + _cond_str(out), "кратко": _brief(out)}
            if full:
                step["значение"] = out
            trace.append(step)
            if errs:
                return NOT_KNOWN, trace, "блок %s нарушил тип %s: %s" % (b.name, otype, errs)
            if self.types.flag(otype, "конечный"):
                thr = b.passport.get("порог_ответа")       # знание само объявило, ниже какой уверенности оно «не уверено»
                if thr is not None and isinstance(out, dict) and isinstance(out.get("p"), (int, float)) and out["p"] < thr:
                    return NOT_KNOWN, trace, "знание %s не уверено: p=%.3f < порога блока %.3f" % (b.name, out["p"], thr)
                return out, trace, None
            cands = self._consumers(otype, out)
            if not cands:
                return NOT_KNOWN, trace, "нет блока для %s%s" % (otype, _cond_str(out))
            if len(cands) > 1:
                return NOT_KNOWN, trace, "неоднозначно: %s" % [c.name for c in cands]
            b, tname, value = cands[0], otype, out
        return NOT_KNOWN, trace, "цепочка длиннее %d шагов" % MAX_STEPS

    def _finish(self, text, answer, trace, claims, reason):
        if answer == NOT_KNOWN:
            short = NOT_KNOWN
        else:
            short = {k: answer[k] for k in ("область", "id", "итог", "p", "текст") if k in answer}
        rec = {"вопрос": text, "ответ": short, "путь": [s["блок"] for s in trace], "шаги": trace}
        if claims:
            rec["заявки"] = claims
        if reason:
            rec["отказ"] = reason
        if self.trace_path:
            with open(self.trace_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return answer, rec

    # ================= контроль =================
    def control(self):
        """Прогон контрольных наборов всех подключённых блоков через полный маршрут.
        Возвращает {блок: {"всего", "ответил_этот_блок", "совпало_с_ожиданием", "ответы": [...]}}."""
        out = {}
        for b in sorted(self.blocks.values(), key=lambda x: x.name):
            cf = (b.passport.get("контроль") or {}).get("файл")
            if not cf:
                continue
            with open(os.path.join(b.path, cf), encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
            got, mine, same = [], 0, 0
            for r in rows:
                ans, rec = self.ask(r["запрос"])
                key = None if ans == NOT_KNOWN else json.dumps(rec["ответ"], ensure_ascii=False, sort_keys=True)
                got.append(key)
                if rec["путь"] and rec["путь"][-1] == b.name:
                    mine += 1
                if ans != NOT_KNOWN and all(ans.get(k) == v for k, v in r["ожидание"].items()):
                    same += 1
            out[b.name] = {"всего": len(rows), "ответил_этот_блок": mine, "совпало_с_ожиданием": same, "ответы": got}
        return out

    def attach_checked(self, block_dir):
        """Подключить и сразу показать, как изменились ответы других блоков на их контроле."""
        before = self.control()
        ok, msg = self.attach(block_dir)
        if not ok:
            return ok, msg, None
        after = self.control()
        report = {}
        for name, a in after.items():
            if name in before:
                bb = before[name]
                changed = sum(x != y for x, y in zip(bb["ответы"], a["ответы"]))
                report[name] = {"всего": a["всего"], "изменилось_ответов": changed,
                                "ответил_этот_блок": "%d → %d" % (bb["ответил_этот_блок"], a["ответил_этот_блок"])}
            else:
                report[name] = {"новый": True, "всего": a["всего"], "ответил_этот_блок": a["ответил_этот_блок"],
                                "совпало_с_ожиданием": a["совпало_с_ожиданием"]}
        return ok, msg, report

    # ================= параметры =================
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
        """Дообучить ОДИН блок: data = [(значение типа входа, правильный выход)]. Новая версия — в своей папке."""
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
        for extra in ("контроль",):
            cf = (b.passport.get(extra) or {}).get("файл")
            if cf:
                shutil.copy(os.path.join(b.path, cf), os.path.join(out_dir, cf))
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


def _brief(v):
    if not isinstance(v, dict):
        return None
    out = {}
    for k in ("область", "id", "p"):
        if k in v:
            out[k] = round(v[k], 4) if isinstance(v[k], float) else v[k]
    if "p_область" in v and v.get("область") in v["p_область"]:
        out["p"] = round(v["p_область"][v["область"]], 4)
    if "основы" in v:
        out["основ"] = len(v["основы"])
    if "замены" in v:
        out["замены"] = v["замены"]
    if "текст" in v:
        out["текст"] = v["текст"][:200]
    return out
