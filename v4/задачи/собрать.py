# -*- coding: utf-8 -*-
"""Сборка наборов для блока задач (задачи/наборы/*.jsonl) и словаря кусков слов (sentencepiece, обучен на train).
  train: генератор 30 000 ru + 30 000 en (11 видов) + GSM8K train ru и en без 200+200 для dev;
  dev:   генератор 500 ru + 500 en, GSM8K 200 ru + 200 en;
  test (только проверка): ген_знакомые 500+500, ген_новые (виды T8,T12,T14) 300+300,
        gsm8k_test ru/en (1319), mgsm ru/en (250).
Запуск: python задачи/собрать.py"""
import csv
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V4 = os.path.dirname(HERE)
DATA = os.path.join(V4, "данные")
OUT = os.path.join(HERE, "наборы")
sys.path.insert(0, HERE)
import генератор as GEN  # noqa: E402

NL = "⏎"


def gsm(lang, split):
    with open(os.path.join(DATA, "gsm8k_%s_%s.jsonl" % (lang, split)), encoding="utf-8") as f:
        return [dict(json.loads(l), источник="gsm8k", язык=lang) for l in f if l.strip()]


def mgsm(lang):
    rows = []
    with open(os.path.join(DATA, "mgsm_%s.tsv" % lang), encoding="utf-8") as f:
        for q, a in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            rows.append({"question": q, "answer": "#### %s" % a.strip(), "источник": "mgsm", "язык": lang})
    return rows


def gen(kinds, lang, n, seed, seen):
    rnd, rows = random.Random(seed), []
    while len(rows) < n:
        d = GEN.make(rnd.choice(kinds), lang, rnd)
        if d["question"] in seen:
            continue
        seen.add(d["question"])
        rows.append(dict(d, источник="генератор"))
    return rows


def final(ans):
    return ans.split("####")[-1].strip().replace(",", "").replace(" ", "")


def write(name, rows):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + ".jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            r = dict(r, итог=final(r["answer"]))
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("%-22s %6d  sha256 %s" % (name, len(rows), hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]))


def main():
    known = [k for k in GEN.KINDS if k not in GEN.HELD_OUT]
    seen = set()
    tr = gen(known, "ru", 30000, 1, seen) + gen(known, "en", 30000, 2, seen)
    dv = gen(known, "ru", 500, 3, seen) + gen(known, "en", 500, 4, seen)
    te_known = gen(known, "ru", 500, 5, seen) + gen(known, "en", 500, 6, seen)
    te_new = gen(list(GEN.HELD_OUT), "ru", 300, 7, seen) + gen(list(GEN.HELD_OUT), "en", 300, 8, seen)
    for lang in ("ru", "en"):
        g = sorted(gsm(lang, "train"), key=lambda r: hashlib.md5(r["question"].encode("utf-8")).hexdigest())
        dv += g[:200]
        tr += g[200:]
    random.Random(9).shuffle(tr)
    write("train", tr)
    write("dev", dv)
    write("тест_ген_знакомые", te_known)
    write("тест_ген_новые", te_new)
    for lang in ("ru", "en"):
        write("тест_gsm8k_" + lang, gsm(lang, "test"))
        write("тест_mgsm_" + lang, mgsm(lang))
    # словарь кусков слов — только по train (sentencepiece не открывает пути с кириллицей: учим из памяти, пишем байты сами)
    import io
    import sentencepiece as spm
    lines = []
    for r in tr:
        lines += [r["question"].replace("\n", NL), r["answer"].replace("\n", NL)]
    buf = io.BytesIO()
    spm.SentencePieceTrainer.train(sentence_iterator=iter(lines), model_writer=buf, vocab_size=4000, model_type="bpe",
                                   character_coverage=1.0, split_digits=True, byte_fallback=True,
                                   user_defined_symbols=["<<", ">>", "####", NL], remove_extra_whitespaces=False,
                                   normalization_rule_name="identity", pad_id=0, unk_id=1, bos_id=2, eos_id=3, num_threads=6,
                                   input_sentence_size=2000000, shuffle_input_sentence=True)
    with open(os.path.join(OUT, "куски.model"), "wb") as f:
        f.write(buf.getvalue())
    print("словарь кусков:", os.path.join(OUT, "куски.model"))


if __name__ == "__main__":
    main()
