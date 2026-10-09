# -*- coding: utf-8 -*-
"""Общее для замера флагманов: пути, набор, справочник, текст запроса, разбор ответа модели.

Ничего вне папки флагманы/ не пишет. v6, внешние, рабочий проект — только чтение."""
import hashlib
import json
import os
import re
import sys

sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
БАЗА = os.path.dirname(ROOT)
V6 = os.path.join(БАЗА, "v6")
ВНЕШНИЕ = os.path.join(БАЗА, "внешние")
НАБОР = os.path.join(ROOT, "набор", "набор.jsonl")
ОТВЕТЫ = os.path.join(ROOT, "ответы")
СЫРЫЕ = os.path.join(ROOT, "сырые")
СПРАВОЧНИК = os.path.join(ВНЕШНИЕ, "справочник.json")

ОБЛАСТИ = ("здоровье", "право", "вне")


def jl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def write_jl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def набор():
    """Строки набора в порядке подачи моделям."""
    return jl(НАБОР)


def справочник():
    d = json.load(open(СПРАВОЧНИК, encoding="utf-8"))
    return d["статьи_болезней"], d["правовые_темы"]


# ---------------- запрос ----------------
ИНСТРУКЦИЯ = """Ты — справочная система для призывников в России. На вход — вопросы людей с сайта вопросов и ответов, как они есть: с ошибками, сленгом, лишними подробностями.

Для каждого вопроса определи:

1. area — область:
   • «здоровье» — человек спрашивает, годен ли он (или кто-то) к службе по призыву, возьмут ли в армию с конкретной болезнью или состоянием здоровья, какую категорию годности дадут. Ответ — номер статьи Расписания болезней (Положение о военно-врачебной экспертизе, постановление Правительства РФ № 565).
   • «право» — вопрос о правилах призыва и воинского учёта для призывника: повестки, явка, отсрочки, освобождение, медкомиссия как процедура, призывная комиссия и обжалование её решений, учёт и снятие с учёта, переезд и выезд, документы, ответственность за уклонение, сроки службы по призыву. Ответ — одна тема из списка правовых тем ниже.
   • «вне» — всё остальное: служба по контракту, жизнь и быт в армии, военные вузы, выплаты и пенсии военнослужащим, общие разговоры и мнения об армии, вопросы не про призыв.

2. id — для «здоровье» номер статьи из списка (только число, например "52"), для «право» id темы из списка (точно как в списке). Если подходит несколько — выбери самую точную. Если вопрос про призыв, но ни одна статья или тема не подходит или ты не уверен — пустая строка "". Для «вне» id всегда "".

3. confidence — число от 0 до 1: насколько ты уверен в ответе.

Неверно названная статья или тема может навредить человеку: лучше честно поставить id "", чем угадывать.

Ответ — только JSON, без пояснений:
{"answers": [{"i": <номер вопроса>, "area": "здоровье" | "право" | "вне", "id": "<id или пустая строка>", "confidence": <число от 0 до 1>}]}
По одному элементу на каждый вопрос, в том же порядке."""

СХЕМА = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer"},
                    "area": {"type": "string", "enum": list(ОБЛАСТИ)},
                    "id": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["i", "area", "id", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["answers"],
    "additionalProperties": False,
}


def системный_текст():
    """Инструкция + закрытый список. Без дат и случайностей — текст одинаков для всех запросов (кэшируется)."""
    статьи, темы = справочник()
    parts = [ИНСТРУКЦИЯ, "", "СТАТЬИ РАСПИСАНИЯ БОЛЕЗНЕЙ (id — название):"]
    parts += ["%s — %s" % (x["id"], x["название"]) for x in статьи]
    parts += ["", "ПРАВОВЫЕ ТЕМЫ (id — название):"]
    parts += ["%s — %s" % (x["id"], x["название"]) for x in темы]
    return "\n".join(parts)


def текст_вопросов(rows):
    """Вопросы пачки под номерами 1..n (номера только внутри пачки, без названий наборов)."""
    lines = ["Вопросы:"]
    for n, r in enumerate(rows, 1):
        lines.append("[%d] %s" % (n, re.sub(r"\s+", " ", r["текст"]).strip()))
    return "\n\n".join(lines)


def пачки(rows, size):
    return [rows[k:k + size] for k in range(0, len(rows), size)]


# ---------------- разбор ответа ----------------
_ПУСТО = {"", "null", "none", "нет", "-", "—", "не знаю", "\"\""}


def _json_из_текста(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        pass
    for open_, close in (("{", "}"), ("[", "]")):
        a, b = text.find(open_), text.rfind(close)
        if a != -1 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except ValueError:
                continue
    return None


def _область(v):
    v = str(v or "").strip().lower().strip("«»\"'")
    return {"health": "здоровье", "law": "право", "out": "вне", "none": "вне"}.get(v, v)


def _id(v, area):
    v = "" if v is None else str(v).strip().strip("«»\"'")
    if v.lower() in _ПУСТО:
        return ""
    if area == "здоровье":
        m = re.fullmatch(r"(?:ст(?:атья)?\.?\s*)?0*(\d+)", v, flags=re.I)
        if m:
            return m.group(1)
    return v


def разобрать(text, n):
    """Ответ модели → {номер в пачке: (область, id, уверенность)}. Неразборчивое пропускается."""
    data = _json_из_текста(text)
    items = data.get("answers") if isinstance(data, dict) else data
    out = {}
    if not isinstance(items, list):
        return out
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            i = int(it.get("i"))
        except (TypeError, ValueError):
            continue
        area = _область(it.get("area", it.get("область")))
        if not 1 <= i <= n or area not in ОБЛАСТИ:
            continue
        idv = "" if area == "вне" else _id(it.get("id"), area)
        try:
            conf = float(it.get("confidence", it.get("уверенность")))
            conf = min(1.0, max(0.0, conf))
        except (TypeError, ValueError):
            conf = None
        out[i] = (area, idv, conf)
    return out
