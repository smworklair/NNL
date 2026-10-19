# -*- coding: utf-8 -*-
"""Ядро NNL v8 — обычная программа на Python, только стандартная библиотека (numpy не импортирует).
Ни одного обученного числа. Ничего не знает о здоровье, праве или любой другой области: всё это — в языке, схемах и паспортах.

Шеф на кухне. Само не готовит. Отвечает за:
  1. Подключение и снятие блоков с проверкой паспорта, хешей, языка и бюджета (на ходу, без перезапуска).
  2. Сборку подключённых блоков в одну сеть по схеме (схемы/*.json — техкарта задачи).
  3. Общую шину и формулу смешивания: блоки кладут на шину слова языка, ядро складывает их по правилу языка.
  4. Два прохода: в первом каждый блок кладёт свой вклад (оценки понятий), во втором — читает шину с вкладами соседей и даёт
     счёты своих ответов. Блоки не видят друг друга, только шину.
  5. Сборку одного ответа из счётов всех блоков (softmax против опорного «ничего»), «уточнить» и «не знаю».
  6. Журнал: ответ, путь, версии и хеши блоков, что каждый блок положил на шину и сколько вложил в счёт ответа (точное разложение).
  7. Сессии: у каждой своё состояние и журнал; закрытая сессия ничего не оставляет следующей.
  8. Сбой блока: исключение в блоке — ядро отмечает «этого куска нет» и собирает ответ из остального.
  9. Снятие и вставка с замером: насколько изменились ответы остальных.
 10. Заморозку блоков (замороженный блок обучение не меняет — проверяется по хешу).

Числа считает код архитектуры блока (папка архитектуры/), ядро только вызывает его и складывает результаты."""
import datetime
import hashlib
import importlib.util
import json
import math
import os
import sys
import time
import traceback

НЕ_ЗНАЮ = "не знаю"
ОБЯЗАТЕЛЬНО = ("имя", "версия", "роль", "архитектура", "веса", "язык", "пишет", "читает", "ответы", "обучение", "контроль")
ECE_МАКС = 0.10
AUC_МИН = 0.80


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sigmoid(z):
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


# ======================================================================== язык
class Язык:
    """Загрузчик языка (папка язык/): стандарт.json — слова и их смысл, правила.py — перевод вопроса на язык.
    Правил языка в ядре нет: ядро только загружает их и считает отпечатки."""

    def __init__(self, папка):
        self.папка = os.path.abspath(папка)
        with open(os.path.join(self.папка, "стандарт.json"), encoding="utf-8") as f:
            self.стандарт = json.load(f)
        self.имя = self.стандарт["имя"]
        self.версия = self.стандарт["версия"]
        self.понятия = dict(self.стандарт["понятия"])
        self.правила = _load_module(os.path.join(self.папка, "правила.py"), "nnl_язык_правила_%d" % id(self))
        files = [os.path.join(self.папка, "правила.py")]
        sb = os.path.join(self.папка, "snowball_ru")
        files += sorted(os.path.join(sb, f) for f in os.listdir(sb) if f.endswith(".py"))
        h = hashlib.sha256()
        for p in files:
            h.update(os.path.relpath(p, self.папка).replace(os.sep, "/").encode("utf-8"))
            with open(p, "rb") as f:
                h.update(f.read().replace(b"\r\n", b"\n"))
        h.update(json.dumps([self.стандарт["формы_токенов"], self.стандарт["метки"]], ensure_ascii=False, sort_keys=True).encode("utf-8"))
        self.отпечаток_правил = h.hexdigest()
        общее = self.стандарт["смысл_чисел_шины"] + "\n" + self.стандарт["правило_смешивания"]
        self._fp = {k: sha256_text(k + "\n" + v + "\n" + общее) for k, v in self.понятия.items()}
        self.отпечаток_ответов = sha256_text(json.dumps(self.стандарт["ответы"], ensure_ascii=False, sort_keys=True))

    def отпечаток(self, понятие):
        return self._fp.get(понятие)

    def области(self):
        return [k.split(":", 1)[1] for k in self.понятия if k.startswith("область:")]

    def ответ_допустим(self, ответ):
        parts = ответ.split(":", 2)
        return len(parts) == 3 and parts[0] == "ответ" and ("область:" + parts[1]) in self.понятия and parts[2] != ""

    def перевести(self, текст):
        return self.правила.разобрать(текст)

    def паспорт_языка(self, пишет, читает):
        """Что блок должен записать в паспорт при обучении (используется обучением, а не ядром при работе)."""
        return {"имя": self.имя, "версия": self.версия, "правила": self.отпечаток_правил, "ответы": self.отпечаток_ответов,
                "понятия": {k: self._fp[k] for k in sorted(set(пишет) | set(читает))}}


# ======================================================================== схема
class Схема:
    """Техкарта задачи: какие блоки участвуют, сколько проходов, формула смешивания и сборки, когда «не знаю».
    Другая задача — другая схема, ядро то же."""
    ПОЛЯ = {"имя": "без схемы", "блоки": None, "проходов": 2, "смешивание": "среднее", "веса_смешивания": {},
            "сборка": "softmax против «ничего»", "порог_ответа": 0.5, "порог_уточнить": 0.5, "бюджет_чисел": None,
            "заморожены": []}

    def __init__(self, d=None):
        d = dict(d or {})
        for k, v in self.ПОЛЯ.items():
            setattr(self, k, d.get(k, v))
        if self.проходов not in (1, 2):
            raise ValueError("проходов должно быть 1 или 2")
        if self.смешивание not in ("среднее", "сумма"):
            raise ValueError("смешивание: «среднее» или «сумма»")
        self.данные = d

    @classmethod
    def из_файла(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))


# ======================================================================== блок
class Блок:
    def __init__(self, папка, паспорт, arch, obj):
        self.папка, self.паспорт, self.arch, self.obj = папка, паспорт, arch, obj
        self.имя = паспорт["имя"]
        self.версия = паспорт["версия"]
        self.sha256 = паспорт["веса"]["sha256"]
        self.пишет = list(паспорт["пишет"])
        self.читает = list(паспорт["читает"])
        self.ответы = list(паспорт["ответы"])
        self.чисел = int(паспорт["веса"]["чисел"])

    def кратко(self):
        return {"блок": self.имя, "версия": self.версия, "sha256": self.sha256[:12]}


# ======================================================================== сессия
class Сессия:
    """Состояние одной сессии: свой журнал и общая картина сессии (сколько вопросов, средние числа шины по областям,
    последние ответы). Картина видна в журнале; в ответы она не подмешивается (блоки не учились на диалогах).
    Закрытие всё стирает; следующей сессии ничего не передаётся."""
    _счёт = 0

    def __init__(self, ядро):
        Сессия._счёт += 1
        self.ид = "с%d-%s" % (Сессия._счёт, datetime.datetime.now().strftime("%H%M%S"))
        self.ядро = ядро
        self.журнал = []
        self.картина = {"вопросов": 0, "области": {}, "последние_ответы": []}
        self.открыта = True

    def _учесть(self, запись):
        к = self.картина
        к["вопросов"] += 1
        for понятие, v in (запись.get("шина") or {}).items():
            if понятие.startswith("область:"):
                o = понятие.split(":", 1)[1]
                старое = к["области"].get(o, 0.0)
                к["области"][o] = round(старое + (v - старое) / к["вопросов"], 4)
        a = запись["ответ"]
        к["последние_ответы"] = (к["последние_ответы"] + [a if isinstance(a, str) else "%s:%s:%s" % (a["вид"], a["область"], a.get("id", ""))])[-5:]

    def спросить(self, текст):
        if not self.открыта:
            raise RuntimeError("сессия закрыта")
        return self.ядро.спросить(текст, сессия=self)

    def закрыть(self):
        self.журнал = []
        self.картина = {"вопросов": 0, "области": {}, "последние_ответы": []}
        self.открыта = False


# ======================================================================== ядро
class Ядро:
    def __init__(self, язык, архитектуры, схема=None, журнал_файл=None):
        self.язык = язык if isinstance(язык, Язык) else Язык(язык)
        self.arch_dir = os.path.abspath(архитектуры)
        self.схема = схема if isinstance(схема, Схема) else (Схема.из_файла(схема) if схема else Схема())
        self.журнал_файл = журнал_файл
        self.блоки = {}               # имя -> Блок (порядок подключения на ответ не влияет: сложение и softmax симметричны)
        self._arch = {}
        self._владелец = {}            # ответ -> имя блока

    # ------------------------------------------------------------ архитектуры
    def _архитектура(self, имя):
        if имя not in self._arch:
            p = os.path.join(self.arch_dir, имя + ".py")
            if not os.path.exists(p):
                raise ValueError("нет кода архитектуры %r" % имя)
            if self.arch_dir not in sys.path:
                sys.path.insert(0, self.arch_dir)
            self._arch[имя] = _load_module(p, "nnl_arch_%s_%d" % (имя, id(self)))
        return self._arch[имя]

    # ------------------------------------------------------------ проверка паспорта
    def проверить_паспорт(self, папка):
        """(паспорт, ошибки). Только чтение файлов; блок не подключается."""
        pp = os.path.join(папка, "паспорт.json")
        if not os.path.exists(pp):
            return None, ["нет паспорт.json"]
        with open(pp, encoding="utf-8") as f:
            ps = json.load(f)
        errs = ["в паспорте нет поля %r" % k for k in ОБЯЗАТЕЛЬНО if k not in ps]
        if errs:
            return ps, errs
        L, я = ps["язык"], self.язык
        if L.get("имя") != я.имя:
            errs.append("блок говорит на языке %r, ядро — на %r" % (L.get("имя"), я.имя))
        if L.get("правила") != я.отпечаток_правил:
            errs.append("правила языка изменились с тех пор, как блок учился (отпечаток правил не совпадает)")
        if ps["ответы"] and L.get("ответы") != я.отпечаток_ответов:
            errs.append("смысл счёта ответа в языке изменился (отпечаток ответов не совпадает)")
        for k in list(ps["пишет"]) + list(ps["читает"]):
            if k not in я.понятия:
                errs.append("понятия %r нет в языке" % k)
            elif L.get("понятия", {}).get(k) != я.отпечаток(k):
                errs.append("смысл понятия %r в языке изменился (отпечаток не совпадает)" % k)
        if len(set(ps["ответы"])) != len(ps["ответы"]):
            errs.append("в списке ответов есть повторы")
        bad = [a for a in ps["ответы"] if not я.ответ_допустим(a)]
        if bad:
            errs.append("ответы не по форме языка «ответ:<область>:<id>» или область не зарегистрирована: %s" % bad[:3])
        wp = os.path.join(папка, ps["веса"].get("файл", ""))
        if not os.path.isfile(wp):
            errs.append("нет файла весов %r" % ps["веса"].get("файл"))
        elif sha256_file(wp) != ps["веса"].get("sha256"):
            errs.append("файл весов не совпадает с паспортом (sha256)")
        cp = os.path.join(папка, ps["контроль"].get("файл", ""))
        if not os.path.isfile(cp):
            errs.append("нет контрольного набора %r" % ps["контроль"].get("файл"))
        return ps, errs

    # ------------------------------------------------------------ проверка языка блока на его контроле
    def проверить_язык_блока(self, блок, вопросов=None):
        """Числа, которые блок пишет на шину, должны значить то, что сказано в языке: откалиброванный логарифм шансов.
        Для каждого понятия с метками в контроле: ECE ≤ 0,10 и AUC ≥ 0,80 (если есть ≥ 10 «да» и ≥ 10 «нет»)."""
        cp = os.path.join(блок.папка, блок.паспорт["контроль"]["файл"])
        rows = []
        with open(cp, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        if вопросов:
            rows = rows[:вопросов]
        vals = {k: [] for k in блок.пишет}
        for r in rows:
            toks = self.язык.перевести(r["вопрос"])["токены"]
            c = блок.arch.проход1(блок.obj, toks)
            for k, y in (r.get("понятия") or {}).items():
                if k in vals and y is not None:
                    vals[k].append((_sigmoid(c[k]), int(y)))
        отчёт, errs = {}, []
        for k, pv in vals.items():
            pos = sum(y for _, y in pv)
            neg = len(pv) - pos
            if pos < 10 or neg < 10:
                отчёт[k] = {"да": pos, "нет": neg, "проверено": False}
                continue
            ece = _ece(pv)
            auc = _auc(pv)
            ok = ece <= ECE_МАКС and auc >= AUC_МИН
            отчёт[k] = {"да": pos, "нет": neg, "ECE": round(ece, 4), "AUC": round(auc, 4), "проверено": True, "ок": ok}
            if not ok:
                errs.append("понятие %r: ECE %.3f, AUC %.3f — число не значит то, что сказано в языке" % (k, ece, auc))
        return отчёт, errs

    # ------------------------------------------------------------ подключение
    def подключить(self, папка, проверять_язык=True):
        """Подключить блок на ходу. (True, имя, отчёт) или (False, причины, отчёт)."""
        ps, errs = self.проверить_паспорт(папка)
        if errs:
            return False, errs, None
        if ps["имя"] in self.блоки:
            return False, ["блок с именем %r уже подключён" % ps["имя"]], None
        clash = [a for a in ps["ответы"] if a in self._владелец]
        if clash:
            return False, ["ответы уже есть у другого блока: %s (у ответа один хозяин)" % clash[:3]], None
        if self.схема.блоки is not None and ps["имя"] not in self.схема.блоки:
            return False, ["блока %r нет в схеме %r" % (ps["имя"], self.схема.имя)], None
        бюджет = self.схема.бюджет_чисел
        if бюджет is not None and self.чисел_всего() + int(ps["веса"]["чисел"]) > бюджет:
            return False, ["превышен бюджет чисел схемы: %d + %d > %d" % (self.чисел_всего(), ps["веса"]["чисел"], бюджет)], None
        try:
            arch = self._архитектура(ps["архитектура"])
            obj = arch.загрузить(os.path.join(папка, ps["веса"]["файл"]), ps)
        except Exception as e:  # noqa: BLE001
            return False, ["код архитектуры не загрузил веса: %r" % e], None
        if arch.чисел(obj) != int(ps["веса"]["чисел"]):
            return False, ["в весах %d чисел, в паспорте %d" % (arch.чисел(obj), ps["веса"]["чисел"])], None
        if list(arch.ответы(obj)) != list(ps["ответы"]) or list(arch.пишет(obj)) != list(ps["пишет"]) \
                or list(arch.читает(obj)) != list(ps["читает"]):
            return False, ["ответы, «пишет» или «читает» в весах не совпадают с паспортом"], None
        b = Блок(папка, ps, arch, obj)
        отчёт = None
        if проверять_язык and b.пишет:
            отчёт, lerr = self.проверить_язык_блока(b)
            if lerr:
                return False, lerr, отчёт
        self.блоки[b.имя] = b
        for a in b.ответы:
            self._владелец[a] = b.имя
        return True, b.имя, отчёт

    def снять(self, имя):
        b = self.блоки.pop(имя, None)
        if b is None:
            return False
        for a in b.ответы:
            self._владелец.pop(a, None)
        return True

    def чисел_всего(self):
        return sum(b.чисел for b in self.блоки.values())

    def заморожен(self, имя):
        return имя in (self.схема.заморожены or [])

    def параметры(self, имя):
        b = self.блоки[имя]
        return b.arch.параметры(b.obj)

    # ------------------------------------------------------------ работа
    def сессия(self):
        return Сессия(self)

    def _смешать(self, вклады):
        """Формула смешивания из схемы. вклады: {блок: {понятие: число}} → шина {понятие: число}, писатели {понятие: [(блок, вес)]}."""
        писатели = {}
        for имя, c in вклады.items():
            w = float(self.схема.веса_смешивания.get(имя, 1.0))
            for k in c:
                писатели.setdefault(k, []).append((имя, w))
        шина = {}
        for k, ws in писатели.items():
            s = sum(w * вклады[n][k] for n, w in ws)
            шина[k] = s / sum(w for _, w in ws) if self.схема.смешивание == "среднее" else s
        return шина, писатели

    def _доля(self, писатели_k, имя):
        """Какая доля значения понятия на шине пришла от блока (по формуле смешивания)."""
        tot = sum(w for _, w in писатели_k)
        for n, w in писатели_k:
            if n == имя:
                return w / tot if self.схема.смешивание == "среднее" else w
        return 0.0

    def спросить(self, текст, сессия=None, подробно=True):
        """Один вопрос через всю сеть. Возвращает (ответ, запись журнала). Ответ — dict или НЕ_ЗНАЮ."""
        t0 = time.time()
        разбор = self.язык.перевести(текст)
        токены = разбор["токены"]
        блоки = list(self.блоки.values())
        if self.схема.блоки is not None:
            блоки = [b for b in блоки if b.имя in self.схема.блоки]
        сбои = {}
        # ---- проход 1: каждый блок кладёт на шину свои оценки понятий
        вклады = {}
        for b in блоки:
            if not b.пишет:
                continue
            try:
                c = b.arch.проход1(b.obj, токены)
                if set(c) != set(b.пишет) or not all(isinstance(v, float) and math.isfinite(v) for v in c.values()):
                    raise ValueError("блок положил на шину не то, что обещал в паспорте")
                вклады[b.имя] = c
            except Exception as e:  # noqa: BLE001
                сбои[b.имя] = "проход 1: %s" % _коротко(e)
        шина, писатели = self._смешать(вклады)
        # ---- проход 2: каждый блок читает шину с вкладами соседей и даёт счёты своих ответов
        счёты, видел = {}, {}
        for b in блоки:
            if b.имя in сбои or not b.ответы:
                continue
            v = {k: шина[k] for k in b.читает if k in шина} if self.схема.проходов == 2 else {}
            try:
                s = b.arch.проход2(b.obj, токены, v)
                if set(s) != set(b.ответы) or not all(isinstance(x, float) and math.isfinite(x) for x in s.values()):
                    raise ValueError("блок вернул счёты не для своих ответов")
                for a, x in s.items():
                    счёты[a] = x
                видел[b.имя] = v
            except Exception as e:  # noqa: BLE001
                сбои[b.имя] = "проход 2: %s" % _коротко(e)
        # ---- сборка: softmax против опорного «ничего» (счёт 0)
        m = max([0.0] + list(счёты.values()))
        z = math.exp(-m) + sum(math.exp(x - m) for x in счёты.values())
        p = {a: math.exp(x - m) / z for a, x in счёты.items()}
        p_ничего = math.exp(-m) / z
        порядок = sorted(p, key=lambda a: (-p[a], a))
        области = {k.split(":", 1)[1]: _sigmoid(v) for k, v in шина.items() if k.startswith("область:")}
        причина = None
        if порядок and p[порядок[0]] >= self.схема.порог_ответа:
            a = порядок[0]
            _, обл, ид = a.split(":", 2)
            ответ = {"вид": "ответ", "область": обл, "id": ид, "p": p[a], "блок": self._владелец[a]}
        else:
            обл_ok = {o: q for o, q in области.items() if q >= self.схема.порог_уточнить and
                      any(x.startswith("ответ:%s:" % o) for x in счёты)}
            if обл_ok:
                o = max(обл_ok, key=lambda x: (обл_ok[x], x))
                ответ = {"вид": "уточнить", "область": o, "id": "", "p": обл_ok[o]}
                причина = "область «%s» понятна (%.2f), но ни один ответ не набрал %.2f" % (o, обл_ok[o], self.схема.порог_ответа)
            else:
                ответ = НЕ_ЗНАЮ
                if not блоки:
                    причина = "нет подключённых блоков"
                elif not счёты:
                    причина = "ни один блок не дал счётов"
                else:
                    причина = "ни одна область и ни один ответ не набрали порога (p «ничего» = %.2f)" % p_ничего
        запись = {"вопрос": текст, "ответ": ответ, "причина": причина, "сбои": сбои,
                  "блоки": [b.кратко() for b in блоки], "схема": self.схема.имя, "проходов": self.схема.проходов,
                  "p_ничего": p_ничего, "время_мс": None}
        if подробно:
            запись["разбор"] = {"метки": разбор["метки"], "отрицания": разбор["отрицания"], "токенов": len(токены)}
            запись["шина"] = {k: round(v, 4) for k, v in sorted(шина.items())}
            запись["вклады"] = {n: {k: round(x, 4) for k, x in sorted(c.items())} for n, c in вклады.items()}
            запись["кандидаты"] = [self._разложить(a, счёты[a], p[a], токены, вклады, писатели, видел) for a in порядок[:3]]
        запись["время_мс"] = round(1000 * (time.time() - t0), 2)
        if сессия is not None:
            запись["сессия"] = сессия.ид
            запись["номер"] = len(сессия.журнал) + 1
            сессия.журнал.append(запись)
            сессия._учесть(запись)
            запись["картина_сессии"] = json.loads(json.dumps(сессия.картина, ensure_ascii=False))
        if self.журнал_файл:
            with open(self.журнал_файл, "a", encoding="utf-8") as f:
                f.write(json.dumps(запись, ensure_ascii=False) + "\n")
        return ответ, запись

    def _разложить(self, a, счёт, вер, токены, вклады, писатели, видел):
        """Точное разложение счёта ответа: прямое чтение вопроса блоком-хозяином + вклад каждого блока через шину."""
        хоз = self.блоки[self._владелец[a]]
        r = хоз.arch.разложить(хоз.obj, токены, видел.get(хоз.имя, {}), a)
        по_блокам = {}
        for k, w in r["чтение"].items():
            for n, _ in писатели.get(k, []):
                по_блокам[n] = по_блокам.get(n, 0.0) + w * self._доля(писатели[k], n) * вклады[n][k]
        сумма = r["прямой"] + r["присутствие"] + sum(по_блокам.values())
        return {"ответ": a, "p": round(вер, 4), "счёт": round(счёт, 4), "хозяин": хоз.имя,
                "прямой": round(r["прямой"], 4), "присутствие": round(r["присутствие"], 4),
                "через_шину": {n: round(x, 4) for n, x in sorted(по_блокам.items())},
                "сходится": abs(сумма - счёт) < 1e-3}

    # ------------------------------------------------------------ замеры при снятии и вставке
    def ответы_на(self, вопросы):
        out = []
        for q in вопросы:
            a, _ = self.спросить(q, подробно=False)
            out.append(_ключ(a))
        return out

    def снять_с_замером(self, имя, вопросы):
        """Снять блок и замерить: сколько ответов других блоков изменилось и куда ушли ответы снятого."""
        if имя not in self.блоки:
            return None
        ответы_блока = set(self.блоки[имя].ответы)
        до = self.ответы_на(вопросы)
        self.снять(имя)
        после = self.ответы_на(вопросы)
        return _сравнить(до, после, ответы_блока)

    def подключить_с_замером(self, папка, вопросы, проверять_язык=True):
        до = self.ответы_на(вопросы)
        ok, msg, отчёт = self.подключить(папка, проверять_язык)
        if not ok:
            return ok, msg, None
        после = self.ответы_на(вопросы)
        return ok, msg, _сравнить(до, после, set(self.блоки[msg].ответы))


def _коротко(e):
    tb = traceback.extract_tb(e.__traceback__)
    where = "%s:%d" % (os.path.basename(tb[-1].filename), tb[-1].lineno) if tb else ""
    return "%s: %s (%s)" % (type(e).__name__, e, where)


def _ключ(a):
    if a == НЕ_ЗНАЮ:
        return "не знаю"
    if a["вид"] == "уточнить":
        return "уточнить:" + a["область"]
    return "ответ:%s:%s" % (a["область"], a["id"])


def _сравнить(до, после, ответы_блока):
    """Сравнение ответов до и после снятия/вставки блока. Категории: ответ этого блока, ответ соседа,
    «уточнить» в области этого блока, «уточнить» в другой области, «не знаю». Таблица переходов + изменения ответов соседей."""
    обл = {a.split(":")[1] for a in ответы_блока}

    def кат(x):
        if x in ответы_блока:
            return "ответ блока"
        if x.startswith("ответ:"):
            return "ответ соседа"
        if x.startswith("уточнить:"):
            return "уточнить: область блока" if x.split(":", 1)[1] in обл else "уточнить: другая область"
        return "не знаю"
    переходы = {}
    for x, y in zip(до, после):
        key = "%s → %s" % (кат(x), кат(y))
        переходы[key] = переходы.get(key, 0) + 1
    сос = [(x, y) for x, y in zip(до, после) if кат(x) == "ответ соседа"]
    сос_после = [(x, y) for x, y in zip(до, после) if кат(y) == "ответ соседа"]
    свои = [(x, y) for x, y in zip(до, после) if x in ответы_блока]
    куда = {}
    for x, y in свои:
        k = "не знаю" if y == "не знаю" else ("уточнить" if y.startswith("уточнить") else "другой блок")
        куда[k] = куда.get(k, 0) + 1
    return {"вопросов": len(до),
            "ответов_соседей_до": len(сос), "из_них_изменилось": sum(x != y for x, y in сос),
            "доля_изменений_ответов_соседей": round(sum(x != y for x, y in сос) / max(1, len(сос)), 4),
            "новых_ответов_соседей": sum(1 for x, y in сос_после if x != y and кат(x) != "ответ соседа"),
            "ответов_этого_блока": len(свои), "куда_ушли": куда,
            "любых_изменений_вне_ответов_блока": sum(x != y for x, y in zip(до, после) if x not in ответы_блока and y not in ответы_блока),
            "переходы": dict(sorted(переходы.items()))}


def _ece(pv, bins=10):
    tot, n = 0.0, len(pv)
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        sel = [(p, y) for p, y in pv if (lo <= p < hi) or (i == bins - 1 and p == 1.0)]
        if sel:
            tot += len(sel) / n * abs(sum(p for p, _ in sel) / len(sel) - sum(y for _, y in sel) / len(sel))
    return tot


def _auc(pv):
    pos = sorted(p for p, y in pv if y)
    neg = sorted(p for p, y in pv if not y)
    # доля пар (pos, neg), где pos > neg (ничьи — половина); через сортировку
    allv = sorted([(p, 1) for p in pos] + [(p, 0) for p in neg])
    rank, i, r_pos = 1, 0, 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        avg = (rank + rank + (j - i) - 1) / 2.0
        r_pos += avg * sum(1 for t in allv[i:j] if t[1] == 1)
        rank += j - i
        i = j
    return (r_pos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))
