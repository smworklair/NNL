# -*- coding: utf-8 -*-
"""Целостность при вставке/снятии блоков. Запуск: python тест_целостности.py [--шагов 40] [--зерно 1]
Пишет результаты/целостность.json."""
import argparse, glob, hashlib, json, os, random, sys, tempfile
V4 = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, V4)
from ядро import NOT_KNOWN, Kernel

TY, AR = os.path.join(V4, "типы"), os.path.join(V4, "архитектуры")
SP, TK = os.path.join(V4, "блоки_раздел"), os.path.join(V4, "блоки_задачи")
BLOCKS = {}
for a in ("здоровье", "право", "команды"):
    BLOCKS[a + ".заявка"] = os.path.join(SP, a + ".заявка"); BLOCKS[a] = os.path.join(SP, a)
BLOCKS["задачи.заявка"] = os.path.join(TK, "задачи.заявка"); BLOCKS["задачи"] = os.path.join(TK, "задачи_малый_с2")
AREAS = ("здоровье", "право", "команды", "задачи")

def tree_hash():
    h = {}
    for root in (SP, TK, os.path.join(V4, "типы"), os.path.join(V4, "измеритель")):
        for p in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
            if os.path.isfile(p) and "__pycache__" not in p and "_без_калькулятора" not in p:
                h[os.path.relpath(p, V4)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return h

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--шагов", type=int, default=40); ap.add_argument("--зерно", type=int, default=1)
    a = ap.parse_args(); rnd = random.Random(a.зерно)
    bench = [json.loads(l) for l in open(os.path.join(V4, "измеритель", "шаг2.jsonl"), encoding="utf-8")]
    qs = [r["вопрос"] for r in bench if r["область"] == "здоровье"][:120] + [r["вопрос"] for r in bench if r["область"] == "право"][:80] \
        + [r["вопрос"] for r in bench if r["область"] == "команды"][:80]
    tasks = [json.loads(l)["question"] for l in open(os.path.join(V4, "задачи", "наборы", "тест_ген2_знакомые.jsonl"), encoding="utf-8")][::100][:10]
    qs += tasks
    before_files = tree_hash()
    trace = os.path.join(tempfile.gettempdir(), "nnl_trace_целостность.jsonl")
    if os.path.exists(trace): os.remove(trace)
    k = Kernel(TY, AR, trace_path=trace)
    for n, p in BLOCKS.items():
        ok, msg = k.attach(p); assert ok, (n, msg)
    ref = [k.ask(q)[1] for q in qs]
    ref_path = [r["путь"] for r in ref]; ref_ans = [json.dumps(r["ответ"], sort_keys=True, ensure_ascii=False) for r in ref]
    attached = set(BLOCKS); asked = len(qs)
    viol_same = viol_nk = checked_same = checked_nk = leaks = broken_claim_q = 0
    log = []
    for step in range(a.шагов):
        absent = [n for n in BLOCKS if n not in attached]
        if absent and (rnd.random() < 0.5 or len(attached) <= 2):
            n = rnd.choice(absent); ok, msg = k.attach(BLOCKS[n]); assert ok, (n, msg); attached.add(n); act = "вернули " + n
        else:
            area = rnd.choice(AREAS); kind = rnd.choice(("знание", "заявка", "оба"))
            names = {"знание": [area], "заявка": [area + ".заявка"], "оба": [area, area + ".заявка"]}[kind]
            for n in names:
                if n in attached: k.detach(n); attached.discard(n)
            act = "сняли %s %s" % (kind, area)
        got = [k.ask(q)[1] for q in qs]; asked += len(qs)
        for i, g in enumerate(got):
            path = ref_path[i]
            if path and all(b in attached for b in path):
                checked_same += 1
                if json.dumps(g["ответ"], sort_keys=True, ensure_ascii=False) != ref_ans[i]: viol_same += 1
            elif path and path[0] in attached and path[-1] not in attached and len(path) == 2:
                checked_nk += 1                        # заявка жива, знание снято -> обязано быть «не знаю»
                if g["ответ"] != NOT_KNOWN: viol_nk += 1
            elif path and path[0] not in attached:
                broken_claim_q += 1
                if g["ответ"] != NOT_KNOWN: leaks += 1
        log.append(act)
    for n in list(BLOCKS):
        if n not in attached: assert k.attach(BLOCKS[n])[0]
    final = [json.dumps(k.ask(q)[1]["ответ"], sort_keys=True, ensure_ascii=False) for q in qs]; asked += len(qs)
    same_final = sum(x == y for x, y in zip(final, ref_ans))
    after_files = tree_hash()
    changed = [f for f in before_files if after_files.get(f) != before_files[f]]; added = [f for f in after_files if f not in before_files]
    lines = sum(1 for _ in open(trace, encoding="utf-8"))
    out = {"шагов": a.шагов, "вопросов_на_шаг": len(qs), "проверено_путь_цел": checked_same, "нарушений_путь_цел": viol_same,
           "проверено_знание_снято_заявка_жива": checked_nk, "нарушений_не_знаю": viol_nk,
           "вопросов_со_снятой_заявкой": broken_claim_q, "из_них_ушли_к_соседу": leaks,
           "после_возврата_всех_блоков_совпало": "%d/%d" % (same_final, len(qs)),
           "файлов_изменилось": changed, "файлов_добавилось": added, "файлов_под_наблюдением": len(before_files),
           "вопросов_задано": asked, "записей_следа": lines, "блоков_в_ядре_в_конце": len(k.blocks), "чисел_в_конце": k.total_numbers(),
           "шаги": log}
    json.dump(out, open(os.path.join(V4, "результаты", "целостность.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print({k2: v for k2, v in out.items() if k2 != "шаги"})
if __name__ == "__main__":
    main()
