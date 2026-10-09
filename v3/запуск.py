# -*- coding: utf-8 -*-
"""Единый запуск v3: измеритель (bench) + проверки К1–К4 + шаг 5 (замена блока области) + сравнение с монолитом.

Блоки и монолит должны быть уже обучены (обучение/*.py). Скрипт ничего не обучает, кроме дообучения в К4
(новая версия блока «право» пишется в блоки/право@2, исходный блок не трогается и возвращается после проверки).
Пишет: результаты/итог.json, результаты/ответы_*.jsonl, результаты/след_база.jsonl; печатает сводку.
Запуск: python запуск.py
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

V3 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):  # консоль Windows/PyCharm: печать стрелок и кириллицы без ошибок
    sys.stdout.reconfigure(encoding="utf-8")
TYPES = os.path.join(V3, "типы")
ARCH = os.path.join(V3, "архитектуры")
BLOCKS = os.path.join(V3, "блоки")
RES = os.path.join(V3, "результаты")
sys.path.insert(0, V3)
sys.path.insert(0, ARCH)

from ядро import NOT_KNOWN, Kernel  # noqa: E402
from ядро.типы import sha256_file  # noqa: E402
from обучение import данные  # noqa: E402
import общее as G  # noqa: E402
import мешок  # noqa: E402

DOM = list(данные.DOMAINS)
OUT = {}


def say(*a):
    print(*a, flush=True)


def bd(name):
    return os.path.join(BLOCKS, name)


def kernel(trace=None):
    return Kernel(TYPES, ARCH, trace)


def attach(k, *names):
    for n in names:
        ok, msg = k.attach(bd(n))
        if not ok:
            raise SystemExit("не подключился %s: %s" % (n, msg))


def run(k, bench, full=False):
    return [k.ask(r["вопрос"], full=full)[1] for r in bench]


def is_ok(r, rec):
    a = rec["ответ"]
    return a != NOT_KNOWN and a["область"] == r["область"] and a["id"] == r["ответ"]


def score(bench, recs):
    t = {d: {"вопросов": 0, "верно": 0, "не_знаю": 0, "ответ_другой_области": 0} for d in DOM}
    for r, rec in zip(bench, recs):
        s = t[r["область"]]
        s["вопросов"] += 1
        a = rec["ответ"]
        if a == NOT_KNOWN:
            s["не_знаю"] += 1
        elif a["область"] != r["область"]:
            s["ответ_другой_области"] += 1
        s["верно"] += is_ok(r, rec)
    for s in t.values():
        s["доля_верных"] = round(s["верно"] / s["вопросов"], 4)
    n = sum(s["вопросов"] for s in t.values())
    c = sum(s["верно"] for s in t.values())
    t["всего"] = {"вопросов": n, "верно": c, "доля_верных": round(c / n, 4)}
    return t


def same_answers(bench, a, b, domain):
    """Сколько ответов по вопросам области domain совпало полностью (область, id, p)."""
    idx = [i for i, r in enumerate(bench) if r["область"] == domain]
    return sum(json.dumps(a[i]["ответ"], ensure_ascii=False) == json.dumps(b[i]["ответ"], ensure_ascii=False) for i in idx), len(idx)


def dump(name, bench, recs):
    with open(os.path.join(RES, name), "w", encoding="utf-8") as f:
        for r, rec in zip(bench, recs):
            f.write(json.dumps({"qid": r["qid"], "область": r["область"], "верный": r["ответ"], "ответ": rec["ответ"],
                                "путь": rec["путь"], "верно": is_ok(r, rec)}, ensure_ascii=False) + "\n")


def file_hashes():
    return {n: sha256_file(os.path.join(BLOCKS, n, "веса.npz")) for n in sorted(os.listdir(BLOCKS))
            if os.path.isfile(os.path.join(BLOCKS, n, "веса.npz"))}


def table_line(t):
    return "здоровье %.4f (%d/%d) | право %.4f (%d/%d) | всего %.4f (%d/%d)" % (
        t["здоровье"]["доля_верных"], t["здоровье"]["верно"], t["здоровье"]["вопросов"],
        t["право"]["доля_верных"], t["право"]["верно"], t["право"]["вопросов"],
        t["всего"]["доля_верных"], t["всего"]["верно"], t["всего"]["вопросов"])


# ---------------------------------------------------------------- К0: ядро без блоков
def check_empty_kernel(bench):
    qfile = os.path.join(RES, "_вопросы.json")
    with open(qfile, "w", encoding="utf-8") as f:
        json.dump([r["вопрос"] for r in bench], f, ensure_ascii=False)
    code = (
        "import sys, json; sys.path.insert(0, %r)\n"
        "from ядро import Kernel, NOT_KNOWN\n"
        "k = Kernel(%r, %r)\n"
        "qs = json.load(open(%r, encoding='utf-8'))\n"
        "ans = [k.ask(q)[0] for q in qs] + [k.ask('как испечь пирог')[0], k.ask('')[0]]\n"
        "print(json.dumps({'блоков': len(k.blocks), 'запросов': len(ans), 'все_не_знаю': all(a == NOT_KNOWN for a in ans),"
        " 'цепочек_в_плане': len(k.plan()), 'numpy_загружен': 'numpy' in sys.modules, 'torch_загружен': 'torch' in sys.modules}))\n"
    ) % (V3, TYPES, ARCH, qfile)
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8")
    os.remove(qfile)
    if p.returncode != 0:
        raise SystemExit(p.stderr)
    r = json.loads(p.stdout.strip().splitlines()[-1])
    files = sorted(os.listdir(os.path.join(V3, "ядро")))
    r["файлы_ядра"] = [f for f in files if f != "__pycache__"]
    r["прошла"] = r["все_не_знаю"] and not r["numpy_загружен"] and not r["torch_загружен"] and r["блоков"] == 0
    return r


# ---------------------------------------------------------------- проверка типов при подключении
def check_type_guard():
    tmp = os.path.join(RES, "_плохие_блоки")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)

    def make(name, src, edit=None, tamper=False):
        d = os.path.join(tmp, name)
        shutil.copytree(bd(src), d)
        pp = os.path.join(d, "паспорт.json")
        with open(pp, encoding="utf-8") as f:
            ps = json.load(f)
        if edit:
            edit(ps)
        with open(pp, "w", encoding="utf-8") as f:
            json.dump(ps, f, ensure_ascii=False)
        if tamper:
            with open(os.path.join(d, "веса.npz"), "ab") as f:
                f.write(b"\0")
        return d

    def law_as_health(ps):
        ps["имя"] = "право_под_видом_здоровья"
        ps["вход"]["условие"]["область"] = "здоровье"
        ps["выход"]["условие"]["область"] = "здоровье"

    cases = {
        "веса права, а паспорт обещает Ответ[здоровье]": make("a", "право", law_as_health),
        "неизвестный тип входа «Картинка»": make("b", "право", lambda ps: ps["вход"].update({"тип": "Картинка"})),
        "файл весов изменён после записи паспорта": make("c", "здоровье", lambda ps: ps.update({"имя": "здоровье_x"}), tamper=True),
        "блок обучен под другие типы (типы_sha256)": make("d", "право", lambda ps: ps.update({"имя": "право_x", "типы_sha256": "0" * 64})),
        "в паспорте нет поля «выход»": make("e", "право", lambda ps: ps.pop("выход")),
        "условие на значение вне перечисления Область": make("f", "право", lambda ps: (ps.update({"имя": "право_y"}), ps["вход"]["условие"].update({"область": "медицина"}))),
    }
    res = {}
    for title, d in cases.items():
        k = kernel()            # только «разбор»: чтобы отказ был из-за типов, а не из-за конфликта входа
        attach(k, "разбор")
        ok, msg = k.attach(d)
        res[title] = {"подключён": ok, "причина": msg if not ok else None}
    k = kernel()
    attach(k, "разбор", "здоровье", "право")
    ok, msg = k.attach(bd("здоровье_2"))
    res["второй блок с тем же входом Разбор[область=здоровье] (здоровье_2 при подключённом здоровье)"] = {"подключён": ok, "причина": msg if not ok else None}
    shutil.rmtree(tmp, ignore_errors=True)
    return {"случаи": res, "прошла": not any(v["подключён"] for v in res.values())}


# ---------------------------------------------------------------- монолит
def monolith_predict(kind, bench, path=None):
    sys.path.insert(0, os.path.join(V3, "обучение"))
    from обучение.обучить_монолит import text_features
    canon = G.load_canon(TYPES)
    vocab, vindex = G.load_vocab(TYPES)
    vset = set(vocab)
    P = G.load_npz(os.path.join(path or os.path.join(V3, "сравнение", kind), "веса.npz"))
    classes = [str(c) for c in P.pop("классы")]
    bag_cfg = {"корзины_пар": 1 << 15, "пары": True}
    recs = []
    for r in bench:
        idx = text_features(r["вопрос"], canon) if kind == "монолит" else \
            мешок.features(canon.reference_parse(r["вопрос"], vset), vindex, bag_cfg)
        pr = G.forward(P, idx)
        d, i = classes[int(np.argmax(pr))].split(":", 1)
        recs.append({"ответ": {"область": d, "id": i, "p": float(pr.max())}, "путь": [kind]})
    return recs, int(sum(v.size for v in P.values()))


def main():
    os.makedirs(RES, exist_ok=True)
    bench = данные.bench()
    say("измеритель:", len(bench), "вопросов;", {d: sum(r["область"] == d for r in bench) for d in DOM})
    hashes_start = file_hashes()
    OUT["хеши_весов_в_начале"] = hashes_start

    # К0 — ядро без блоков
    k0 = check_empty_kernel(bench)
    OUT["К0_ядро_без_блоков"] = k0
    say("\nК0 ядро без блоков:", k0)

    # проверка типов при подключении
    tg = check_type_guard()
    OUT["типы_при_подключении"] = tg
    say("\nПроверка типов при подключении:", "прошла" if tg["прошла"] else "НЕ ПРОШЛА")
    for t, v in tg["случаи"].items():
        say("  -", t, "->", "ПОДКЛЮЧЁН" if v["подключён"] else "отказ: %s" % "; ".join(v["причина"]))

    # ---------- базовый прогон ----------
    tpath = os.path.join(RES, "след_база.jsonl")
    if os.path.exists(tpath):
        os.remove(tpath)
    k = kernel(tpath)
    attach(k, "разбор", "здоровье", "право")
    OUT["подключено"] = k.attached()
    OUT["план"] = k.plan()
    OUT["параметры"] = {n: k.params(n) for n in sorted(k.blocks)}
    say("\nплан цепочек по паспортам:", OUT["план"])
    t0 = time.time()
    base = run(k, bench)
    dt = time.time() - t0
    k.trace_path = None
    sb = score(bench, base)
    OUT["измеритель_цепочка"] = sb
    OUT["мс_на_вопрос_цепочка"] = round(1000 * dt / len(bench), 2)
    dump("ответы_цепочка.jsonl", bench, base)
    say("\nИЗМЕРИТЕЛЬ, цепочка разбор→область:", table_line(sb))

    # ---------- К1 след ----------
    with open(tpath, encoding="utf-8") as f:
        logged = [json.loads(l) for l in f]
    sha = {b["имя"]: b["sha256"] for b in k.attached()}
    bad = 0
    for rec in base:
        a = rec["ответ"]
        if not rec["шаги"] or a == NOT_KNOWN:
            bad += 1
            continue
        if rec["путь"] != ["разбор", a["область"]] or any(s["sha256"] != sha[s["блок"]] for s in rec["шаги"]):
            bad += 1
    k1b = kernel()
    attach(k1b, "право", "здоровье", "разбор")  # другой порядок подключения
    again = run(k1b, bench)
    same = sum(json.dumps(x, ensure_ascii=False, sort_keys=True) == json.dumps(y, ensure_ascii=False, sort_keys=True) for x, y in zip(base, again))
    k1 = {"ответов": len(base), "со_следом_и_верным_путём": len(base) - bad, "записей_в_файле_следа": len(logged),
          "повтор_в_новом_ядре_совпал": same, "пример": base[0]["шаги"], "прошла": bad == 0 and len(logged) == len(base) and same == len(base)}
    OUT["К1_след"] = k1
    say("\nК1 след: со следом %d/%d, в файле %d, повтор (другой порядок подключения) совпал %d/%d -> %s" % (
        k1["со_следом_и_верным_путём"], len(base), len(logged), same, len(base), "прошла" if k1["прошла"] else "НЕ ПРОШЛА"))
    say("   пример следа:", json.dumps(base[0], ensure_ascii=False)[:600])

    # ---------- К2 снятие ----------
    k2 = {}
    for removed in DOM + ["разбор"]:
        kk = kernel()
        attach(kk, "разбор", "здоровье", "право")
        kk.detach(removed)
        recs = run(kk, bench)
        sc = score(bench, recs)
        row = {"таблица": sc}
        if removed in DOM:
            other = [d for d in DOM if d != removed][0]
            n_rm = sc[removed]["вопросов"]
            answered_from_removed = sum(1 for r, rec in zip(bench, recs) if rec["ответ"] != NOT_KNOWN and rec["ответ"]["область"] == removed)
            same_o, n_o = same_answers(bench, base, recs, other)
            kk2 = kernel()
            attach(kk2, "разбор", "здоровье", "право")
            restored = run(kk2, bench)
            same_back = sum(json.dumps(x["ответ"]) == json.dumps(y["ответ"]) for x, y in zip(base, restored))
            row.update({"ответов_из_снятой_области": answered_from_removed,
                        "не_знаю_по_снятой_области": sc[removed]["не_знаю"], "вопросов_снятой_области": n_rm,
                        "ушли_в_другую_область": sc[removed]["ответ_другой_области"],
                        "другая_область_ответы_совпали": "%d/%d" % (same_o, n_o),
                        "другая_область_доля_до": sb[other]["доля_верных"], "другая_область_доля_после": sc[other]["доля_верных"],
                        "после_возврата_блока_совпало": "%d/%d" % (same_back, len(bench))})
            row["прошла"] = answered_from_removed == 0 and same_o == n_o and same_back == len(bench)
            say("\nК2 снят «%s»: ответов из этой области %d; «не знаю» %d/%d; ушли в «%s» %d (ошибки разбора, были и до снятия);"
                " ответы «%s» совпали %d/%d (доля %.4f -> %.4f); после возврата совпало %d/%d -> %s" % (
                    removed, answered_from_removed, sc[removed]["не_знаю"], n_rm, other, sc[removed]["ответ_другой_области"],
                    other, same_o, n_o, sb[other]["доля_верных"], sc[other]["доля_верных"], same_back, len(bench),
                    "прошла" if row["прошла"] else "НЕ ПРОШЛА"))
        else:
            row["все_не_знаю"] = all(rec["ответ"] == NOT_KNOWN for rec in recs)
            say("\nК2 (дополнительно) снят «разбор»: все ответы «не знаю» -> %s" % row["все_не_знаю"])
        k2[removed] = row
    OUT["К2_снятие"] = k2

    # ---------- К3 дыра ----------
    full = run(k, bench, full=True)
    with open(os.path.join(данные.ROOT, "train", "data", "docs_articles.jsonl"), encoding="utf-8") as f:
        chapter = {a["article_no"]: a["chapter"] for a in map(json.loads, f)}
    attrib = {d: {"верно": 0, "ошибка_блока_разбор": 0, "ошибка_блока_области": 0} for d in DOM}
    groups = {}
    for r, rec in zip(bench, full):
        d = r["область"]
        parsed = rec["шаги"][0]["значение"]
        if is_ok(r, rec):
            attrib[d]["верно"] += 1
        elif parsed["область"] != d:
            attrib[d]["ошибка_блока_разбор"] += 1
        else:
            attrib[d]["ошибка_блока_области"] += 1
        g = ("здоровье: " + chapter[r["ответ"]]) if d == "здоровье" else ("право: " + r["ответ"].split("_")[0])
        groups.setdefault(g, [0, 0])
        groups[g][0] += 1
        groups[g][1] += is_ok(r, rec)
    grp = sorted(({"группа": g, "вопросов": n, "верно": c, "доля": round(c / n, 3)} for g, (n, c) in groups.items()),
                 key=lambda x: (x["доля"], -x["вопросов"]))
    OUT["К3_дыра"] = {"по_областям": {d: dict(sb[d], **attrib[d]) for d in DOM}, "по_группам_худшие_сначала": grp,
                      "снят_блок_здоровье": k2["здоровье"]["таблица"],
                      "прошла": True}
    say("\nК3 таблица по областям (ошибки по блокам):")
    for d in DOM:
        say("  %-9s доля %.4f | верно %d | ошибка блока «разбор» (не та область) %d | ошибка блока «%s» %d" % (
            d, sb[d]["доля_верных"], attrib[d]["верно"], attrib[d]["ошибка_блока_разбор"], d, attrib[d]["ошибка_блока_области"]))
    say("  худшие группы:", "; ".join("%s %.2f (%d)" % (x["группа"], x["доля"], x["вопросов"]) for x in grp[:6]))

    # ---------- анализ потерь (не вместо измерителя, а для объяснения) ----------
    canon = G.load_canon(TYPES)
    vocab, _ = G.load_vocab(TYPES)
    vset = set(vocab)
    oracle, refparse, nonorm = [], [], []
    n_repl, ex_repl, misrouted = 0, [], []
    for r, rec in zip(bench, full):
        parsed = rec["шаги"][0]["значение"]
        v = copy.deepcopy(parsed)
        v["область"] = r["область"]
        oracle.append(k.ask_typed("Разбор", v)[1])
        v2 = copy.deepcopy(parsed)
        v2["основы"], v2["замены"] = canon.reference_parse(r["вопрос"], vset), []
        refparse.append(k.ask_typed("Разбор", v2)[1])
        n_repl += len(parsed["замены"])
        if parsed["замены"] and len(ex_repl) < 15:
            ex_repl.append([z[:2] for z in parsed["замены"]])
        if parsed["область"] != r["область"]:
            misrouted.append({"вопрос": r["вопрос"][:160], "верная_область": r["область"], "p": round(parsed["p_область"][parsed["область"]], 3)})
    OUT["анализ"] = {"цепочка_с_верной_областью": score(bench, oracle),
                     "цепочка_с_эталонным_разбором_типа_вместо_нормализатора": score(bench, refparse),
                     "замен_нормализатора_на_измерителе": n_repl, "примеры_замен": ex_repl, "ошибки_области": misrouted}
    say("\nанализ: с верной областью:", table_line(OUT["анализ"]["цепочка_с_верной_областью"]))
    say("анализ: эталонный разбор типа (без нормализатора):", table_line(OUT["анализ"]["цепочка_с_эталонным_разбором_типа_вместо_нормализатора"]))
    say("анализ: замен нормализатора %d, примеры %s" % (n_repl, ex_repl[:8]))
    say("анализ: ошибки области (%d):" % len(misrouted), misrouted[:6])

    # ---------- К4 параметры ----------
    k4 = {}
    k = kernel()
    attach(k, "разбор", "здоровье", "право")
    before_files = file_hashes()
    before_arrays = {n: copy.deepcopy(k.param_values(n)) for n in k.blocks}
    k.freeze("здоровье")
    k.freeze("разбор")
    try:
        k.finetune("здоровье", [])
        k4["замороженный_блок_дообучился"] = True
    except PermissionError as e:
        k4["замороженный_блок_дообучился"] = False
        k4["отказ_по_заморозке"] = str(e)
    lex_dev = [({"область": "право", "p_область": {"здоровье": 0.0, "право": 1.0},
                 "основы": canon.reference_parse(t, vset), "замены": []}, y) for t, y in данные.domain_data("право", "dev")]
    newdir = k.finetune("право", lex_dev, {"epochs": 2, "seed": 3})
    after_files = file_hashes()
    after_arrays = {n: k.param_values(n) for n in k.blocks}
    others = {}
    for n in ("разбор", "здоровье", "здоровье_2"):
        a0 = before_arrays.get(n)
        diff = None
        if a0 is not None:
            diff = int(sum(int(np.sum(a0[p] != after_arrays[n][p])) for p in a0))
        others[n] = {"файл_до": before_files[n][:16], "файл_после": after_files[n][:16], "файл_совпал": before_files[n] == after_files[n],
                     "чисел_изменилось_в_памяти": diff}
    old, new = before_arrays["право"], after_arrays["право"]
    changed = int(sum(int(np.sum(old[p] != new[p])) for p in old))
    total = int(sum(old[p].size for p in old))
    old_file_same = before_files["право"] == after_files["право"]
    recs_ft = run(k, bench)
    sft = score(bench, recs_ft)
    same_h, n_h = same_answers(bench, base, recs_ft, "здоровье")
    k4.update({"дообучен": "право", "данные": "dev-часть права (%d строк, эталонный разбор, проверены ядром по типу входа)" % len(lex_dev),
               "новая_версия": os.path.relpath(newdir, V3), "исходный_файл_права_не_тронут": old_file_same,
               "в_праве_изменилось_чисел": "%d из %d" % (changed, total), "другие_блоки": others,
               "ответы_здоровья_совпали": "%d/%d" % (same_h, n_h), "измеритель_после_дообучения": sft,
               "параметры_права_новой_версии": k.params("право")["всего_чисел"]})
    k4["прошла"] = (not k4["замороженный_блок_дообучился"]) and all(v["файл_совпал"] for v in others.values()) \
        and all(v["чисел_изменилось_в_памяти"] in (0, None) for v in others.values()) and changed > 0 and old_file_same and same_h == n_h
    OUT["К4_параметры"] = k4
    say("\nК4: заморозка «здоровье» не дала дообучить: %s; дообучено «право» -> %s, изменилось чисел %s" % (
        not k4["замороженный_блок_дообучился"], k4["новая_версия"], k4["в_праве_изменилось_чисел"]))
    for n, v in others.items():
        say("   %-10s файл %s -> %s совпал=%s; изменилось чисел %s" % (n, v["файл_до"], v["файл_после"], v["файл_совпал"], v["чисел_изменилось_в_памяти"]))
    say("   ответы здоровья совпали %d/%d; измеритель с право@2: %s -> %s" % (same_h, n_h, table_line(sft), "прошла" if k4["прошла"] else "НЕ ПРОШЛА"))
    k.unfreeze("здоровье")

    # ---------- шаг 5: замена блока области ----------
    k = kernel()
    attach(k, "разбор", "здоровье", "право")
    ok_conflict, msg_conflict = k.attach(bd("здоровье_2"))
    k.detach("здоровье")
    ok, msg = k.attach(bd("здоровье_2"))
    plan5 = k.plan()
    recs5 = run(k, bench)
    s5 = score(bench, recs5)
    same_l, n_l = same_answers(bench, base, recs5, "право")
    parse_same = sum(json.dumps(a["шаги"][0]) == json.dumps(b["шаги"][0]) for a, b in zip(base, recs5))
    canon5 = G.load_canon(TYPES)
    vset5 = set(G.load_vocab(TYPES)[0])
    ref5 = []
    for r, rec in zip(bench, full):
        v = copy.deepcopy(rec["шаги"][0]["значение"])
        v["основы"], v["замены"] = canon5.reference_parse(r["вопрос"], vset5), []
        ref5.append(k.ask_typed("Разбор", v)[1])
    s5_ref = score(bench, ref5)
    hashes_end = file_hashes()
    untouched = {n: hashes_start[n] == hashes_end[n] for n in ("разбор", "здоровье", "право", "здоровье_2")}
    with open(os.path.join(bd("здоровье_2"), "паспорт.json"), encoding="utf-8") as f:
        p2 = json.load(f)
    step5 = {"вставка_второго_блока_рядом_с_первым": {"подключён": ok_conflict, "причина": msg_conflict if not ok_conflict else None},
             "замена_подключена": ok, "план": plan5, "новый_блок": {"устройство": p2["устройство"], "зерно": p2["обучение"]["зерно"],
                                                                 "чисел": p2["веса"]["чисел"], "dev": p2["обучение"]["dev"]},
             "измеритель": s5, "здоровье_до": sb["здоровье"]["доля_верных"], "здоровье_после": s5["здоровье"]["доля_верных"],
             "здоровье_2_на_эталонном_разборе_типа": s5_ref["здоровье"]["доля_верных"],
             "ответы_права_совпали": "%d/%d" % (same_l, n_l), "шаг_разбора_совпал": "%d/%d" % (parse_same, len(bench)),
             "файлы_весов_не_менялись_за_весь_прогон": untouched}
    step5["прошла"] = ok and not ok_conflict and same_l == n_l and parse_same == len(bench) and all(untouched.values())
    OUT["шаг5_замена"] = step5
    dump("ответы_цепочка_здоровье_2.jsonl", bench, recs5)
    say("\nШаг 5: второй блок рядом с первым -> %s; замена здоровье -> здоровье_2 (%s, зерно %s): план %s" % (
        "ПОДКЛЮЧЁН" if ok_conflict else "отказ (конфликт входа)", p2["устройство"], p2["обучение"]["зерно"], plan5))
    say("   измеритель:", table_line(s5))
    say("   здоровье_2 на эталонном разборе типа (без блока разбора): %.4f" % s5_ref["здоровье"]["доля_верных"])
    say("   здоровье %.4f -> %.4f; ответы права совпали %d/%d; шаг разбора совпал %d/%d; файлы весов не менялись: %s -> %s" % (
        sb["здоровье"]["доля_верных"], s5["здоровье"]["доля_верных"], same_l, n_l, parse_same, len(bench), untouched,
        "прошла" if step5["прошла"] else "НЕ ПРОШЛА"))

    # ---------- монолит ----------
    mono = {}
    for kind in ("монолит", "монолит_основы"):
        recs, n = monolith_predict(kind, bench)
        mono[kind] = {"измеритель": score(bench, recs), "чисел": n}
        dump("ответы_%s.jsonl" % kind, bench, recs)
    chain_n = sum(OUT["параметры"][n]["всего_чисел"] for n in ("разбор", "здоровье", "право"))
    loss = {}
    for kind in mono:
        mt = mono[kind]["измеритель"]
        loss[kind] = {d: round(100 * (sb[d]["доля_верных"] - mt[d]["доля_верных"]), 2) for d in DOM + ["всего"]}
    OUT["сравнение"] = {"цепочка": {"измеритель": sb, "чисел": chain_n}, **mono, "потеря_пп_цепочка_минус": loss}
    say("\nСРАВНЕНИЕ (доля верных первых ответов):")
    say("   цепочка        (%7d чисел): %s" % (chain_n, table_line(sb)))
    for kind in mono:
        say("   %-14s (%7d чисел): %s" % (kind, mono[kind]["чисел"], table_line(mono[kind]["измеритель"])))
    for kind in loss:
        say("   цепочка минус %s, п.п.: %s" % (kind, loss[kind]))

    OUT["хеши_весов_в_конце"] = hashes_end
    OUT["итог_проверок"] = {"К0": k0["прошла"], "типы": tg["прошла"], "К1": k1["прошла"],
                            "К2": all(k2[d]["прошла"] for d in DOM), "К3": True, "К4": k4["прошла"], "шаг5": step5["прошла"]}
    say("\nИТОГ проверок:", OUT["итог_проверок"])
    with open(os.path.join(RES, "итог.json"), "w", encoding="utf-8") as f:
        json.dump(OUT, f, ensure_ascii=False, indent=1)
    say("записано: результаты/итог.json")


if __name__ == "__main__":
    main()
