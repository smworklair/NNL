# -*- coding: utf-8 -*-
"""Тесты ядра v4 на блоках-пустышках (без нейросетей). Запуск: python тесты/тест_ядра.py
Каждый тест независим; блоки создаются во временной папке тесты/_блоки и удаляются."""
import copy
import json
import os
import shutil
import subprocess
import sys

import numpy as np

V4 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V4)
sys.path.insert(0, os.path.join(V4, "архитектуры"))
from ядро import NOT_KNOWN, Kernel  # noqa: E402
from ядро.схема import sha256_file  # noqa: E402
import общее as G  # noqa: E402

TYPES = os.path.join(V4, "типы")
ARCH = os.path.join(V4, "архитектуры")
TMP = os.path.join(V4, "тесты", "_блоки")
FP = {t: Kernel(TYPES, ARCH).types.fingerprint(t) for t in ("общие:Запрос", "общие:Ответ", "общие:Направление")}


def make(name, words=(), classes=("a", "b", "c"), claim=True, вход="общие:Запрос", выход="общие:Ответ", условие=None, **cfg):
    d = os.path.join(TMP, name)
    os.makedirs(d, exist_ok=True)
    G.save_npz(os.path.join(d, "веса.npz"), {"w": np.zeros(3, dtype=np.float32), "классы": np.array(list(classes))})
    ps = {"имя": name, "версия": 1, "роль": "тест", "область": name, "заявка": claim,
          "вход": dict({"тип": вход}, **({"условие": условие} if условие else {})), "выход": {"тип": выход},
          "архитектура": "пустышка",
          "настройки": dict({"слова": list(words)}, **cfg), "ответы": list(classes),
          "веса": {"файл": "веса.npz", "sha256": sha256_file(os.path.join(d, "веса.npz")), "чисел": 3},
          "типы": {вход: FP[вход], выход: FP[выход]}, "обучение": {"данные": "нет"}}
    if words:
        with open(os.path.join(d, "контроль.jsonl"), "w", encoding="utf-8") as f:
            for w in words:
                f.write(json.dumps({"запрос": "про " + w, "ожидание": {"область": name}}, ensure_ascii=False) + "\n")
        ps["контроль"] = {"файл": "контроль.jsonl"}
    with open(os.path.join(d, "паспорт.json"), "w", encoding="utf-8") as f:
        json.dump(ps, f, ensure_ascii=False)
    return d


def edit(d, fn):
    p = os.path.join(d, "паспорт.json")
    ps = json.load(open(p, encoding="utf-8"))
    fn(ps)
    json.dump(ps, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return d


def K(**kw):
    return Kernel(TYPES, ARCH, **kw)


TESTS = []


def test(f):
    TESTS.append(f)
    return f


@test
def пустое_ядро_не_знаю_и_без_numpy():
    code = ("import sys; sys.path.insert(0, %r)\nfrom ядро import Kernel, NOT_KNOWN\nk = Kernel(%r, %r)\n"
            "r = [k.ask(q)[0] for q in ('про кота', '', 'как испечь пирог')]\n"
            "print(all(x == NOT_KNOWN for x in r), k.plan() == [], 'numpy' in sys.modules, 'torch' in sys.modules)") % (V4, TYPES, ARCH)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.split()
    assert out == ["True", "True", "False", "False"], out


@test
def один_входной_блок_без_заявки():
    k = K()
    ok, _ = k.attach(make("кот", ["кот"], claim=False))
    assert ok
    a, rec = k.ask("что угодно")
    assert a != NOT_KNOWN and rec["путь"] == ["кот"] and "заявки" not in rec


@test
def второй_входной_без_заявки_отклонён():
    k = K()
    assert k.attach(make("кот", ["кот"], claim=True))[0]
    ok, msg = k.attach(make("пёс", ["пёс"], claim=False))
    assert not ok and "заявку" in msg[0], msg


@test
def маршрут_по_заявкам_и_отказ():
    k = K()
    assert k.attach(make("кот", ["кот"]))[0] and k.attach(make("пёс", ["пёс"]))[0]
    assert k.ask("мой кот")[1]["путь"] == ["кот"]
    assert k.ask("мой пёс")[1]["путь"] == ["пёс"]
    a, rec = k.ask("рыба")
    assert a == NOT_KNOWN and "все заявки" in rec["отказ"] and len(rec["заявки"]) == 2
    a, rec = k.ask("кот и пёс")  # равные заявки — по имени, всегда одинаково
    assert rec["путь"] == ["кот"]


@test
def снятие_и_возврат():
    k = K()
    a = make("кот", ["кот"]); b = make("пёс", ["пёс"])
    k.attach(a); k.attach(b)
    before = k.ask("мой пёс")[1]
    k.detach("кот")
    assert k.ask("мой кот")[0] == NOT_KNOWN
    after = k.ask("мой пёс")[1]   # заявок стало меньше, а ответ и путь — те же
    assert after["ответ"] == before["ответ"] and after["путь"] == before["путь"]
    k.attach(a)
    assert k.ask("мой кот")[1]["путь"] == ["кот"]


@test
def плохие_паспорта_отклоняются():
    cases = {
        "другие типы": lambda ps: ps["типы"].update({"общие:Ответ": "0" * 64}),
        "неизвестный тип": lambda ps: ps["вход"].update({"тип": "общие:Картинка"}),
        "нет поля выход": lambda ps: ps.pop("выход"),
        "чисел не столько": lambda ps: ps["веса"].update({"чисел": 999}),
        "ответы не те": lambda ps: ps.update({"ответы": ["x", "y", "z"]}),
        "заявка без функции": lambda ps: ps.update({"архитектура": "нет_такой"}),
    }
    for title, fn in cases.items():
        ok, msg = K().attach(edit(make("плохой_" + str(len(title))), fn))
        assert not ok, title
    d = make("подмена")
    with open(os.path.join(d, "веса.npz"), "ab") as f:
        f.write(b"\0")
    ok, msg = K().attach(d)
    assert not ok and "sha256" in msg[0]


@test
def бюджет():
    k = K(budget=5)
    assert k.attach(make("кот", ["кот"]))[0]
    ok, msg = k.attach(make("пёс", ["пёс"]))
    assert not ok and "бюджет" in msg[0]


@test
def блок_нарушил_тип_получаем_не_знаю():
    k = K()
    k.attach(make("лом", ["лом"], ломает_тип=True))
    a, rec = k.ask("лом")
    assert a == NOT_KNOWN and "не из списка ответов" in rec["отказ"]


@test
def неверная_арифметика_в_тексте_не_знаю():
    k = K()
    k.attach(make("счёт", ["счёт"], classes=("x",), вид="текст", текст="12 - 5 = <<12-5=8>>8"))
    a, rec = k.ask("счёт")
    assert a == NOT_KNOWN and "неверно посчитаны" in rec["отказ"]
    k2 = K()
    k2.attach(make("счёт2", ["счёт"], classes=("x",), вид="текст", текст="12 - 5 = <<12-5=7>>7"))
    assert k2.ask("счёт")[0] != NOT_KNOWN


@test
def заморозка_и_дообучение_одного():
    k = K()
    a = make("кот", ["кот"]); b = make("пёс", ["пёс"])
    k.attach(a); k.attach(b)
    hb = sha256_file(os.path.join(b, "веса.npz")); ha = sha256_file(os.path.join(a, "веса.npz"))
    k.freeze("пёс")
    try:
        k.finetune("пёс", [])
        raise AssertionError("замороженный дообучился")
    except PermissionError:
        pass
    new = k.finetune("кот", [("про кота", "a")])
    assert sha256_file(os.path.join(b, "веса.npz")) == hb and sha256_file(os.path.join(a, "веса.npz")) == ha
    assert float(k.param_values("кот")["w"][0]) == 1.0 and float(k.param_values("пёс")["w"][0]) == 0.0
    assert os.path.basename(new) == "кот@2"


@test
def контроль_при_вставке():
    k = K()
    k.attach(make("кот", ["кот"]))
    ok, _, rep = k.attach_checked(make("пёс", ["пёс"]))
    assert ok and rep["кот"]["изменилось_ответов"] == 0
    ok, _, rep = k.attach_checked(make("жадный", ["жадный"], жадный=True))
    assert ok and rep["кот"]["изменилось_ответов"] == 1 and rep["пёс"]["изменилось_ответов"] == 1


@test
def повтор_даёт_тот_же_след():
    k = K()
    k.attach(make("кот", ["кот"])); k.attach(make("пёс", ["пёс"]))
    qs = ["мой кот", "мой пёс", "рыба", "кот и пёс"]
    r1 = [json.dumps(k.ask(q)[1], sort_keys=True) for q in qs]
    k2 = K()
    k2.attach(make("пёс", ["пёс"])); k2.attach(make("кот", ["кот"]))
    r2 = [json.dumps(k2.ask(q)[1], sort_keys=True) for q in qs]
    assert r1 == r2


@test
def заявка_и_знание_выключить_знание():
    k = K()
    k.attach(make("кот.заявка", ["кот"], classes=("x",), выход="общие:Направление", режим="заявка"))
    k.attach(make("кот.знание", claim=False, вход="общие:Направление", условие={"область": "кот.заявка"}, режим="знание"))
    k.attach(make("пёс", ["пёс"]))
    a, rec = k.ask("мой кот")
    assert rec["путь"] == ["кот.заявка", "кот.знание"] and a != NOT_KNOWN, rec
    before_dog = k.ask("мой пёс")[1]
    k.detach("кот.знание")                 # знание вынуто, заявка осталась — область видна как дыра
    a, rec = k.ask("мой кот")
    assert a == NOT_KNOWN and "нет блока для общие:Направление[область=кот.заявка]" in rec["отказ"], rec
    assert k.ask("мой пёс")[1]["ответ"] == before_dog["ответ"]
    ok, msg = k.attach(make("кот.знание2", claim=False, вход="общие:Направление", условие={"область": "кот.заявка"}, режим="знание"))
    assert ok
    ok, msg = k.attach(make("кот.знание3", claim=False, вход="общие:Направление", условие={"область": "кот.заявка"}, режим="знание"))
    assert not ok and "конфликт" in msg[0]


@test
def новый_тип_в_наборе_не_ломает_старые_блоки():
    d = make("кот", ["кот"])
    p = os.path.join(TYPES, "общие", "набор.json")
    orig = open(p, "rb").read()
    try:
        spec = json.loads(orig.decode("utf-8"))
        spec["типы"]["Пробный"] = {"вид": "строка"}
        open(p, "w", encoding="utf-8").write(json.dumps(spec, ensure_ascii=False))
        ok, msg = K().attach(d)
        assert ok, msg
        spec["типы"]["Ответ"]["поля"]["p"]["до"] = 2.0   # а изменение СВОЕГО типа — ломает
        open(p, "w", encoding="utf-8").write(json.dumps(spec, ensure_ascii=False))
        ok, msg = K().attach(d)
        assert not ok and "отпечаток" in msg[0], msg
    finally:
        open(p, "wb").write(orig)


@test
def спор_заявок_берёт_уверенное_знание():
    a = make("альфа", ["кот"], p=0.6); b = make("бета", ["кот"], p=0.9)
    k = K()
    k.attach(a); k.attach(b)
    assert k.ask("мой кот")[1]["путь"] == ["альфа"]          # без спора: равные заявки → первое имя
    k2 = K(dispute=True)
    k2.attach(a); k2.attach(b)
    ans, rec = k2.ask("мой кот")
    assert rec["путь"] == ["бета"] and ans["p"] == 0.9 and len(rec["спор"]) == 2, rec
    assert k2.ask("рыба")[0] == NOT_KNOWN                   # обе заявки ниже порога — спора нет, «не знаю»


@test
def порог_уверенности_знания():
    k = K()
    k.attach(edit(make("кот", ["кот"], p=0.4), lambda ps: ps.update({"порог_ответа": 0.5})))
    a, rec = k.ask("мой кот")
    assert a == NOT_KNOWN and "не уверено" in rec["отказ"], rec
    k2 = K()
    k2.attach(edit(make("пёс", ["пёс"], p=0.6), lambda ps: ps.update({"порог_ответа": 0.5})))
    assert k2.ask("мой пёс")[0] != NOT_KNOWN


def main():
    failed = 0
    for t in TESTS:
        shutil.rmtree(TMP, ignore_errors=True)
        os.makedirs(TMP)
        try:
            t()
            print("ок      ", t.__name__)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("ПРОВАЛ  ", t.__name__, "—", repr(e))
    shutil.rmtree(TMP, ignore_errors=True)
    print("\nтестов %d, провалено %d" % (len(TESTS), failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
