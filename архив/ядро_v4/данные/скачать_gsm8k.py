# -*- coding: utf-8 -*-
"""Скачивание GSM8K (ru: d0rj/gsm8k-ru, en: openai/gsm8k) через datasets-server HF по 100 строк, с докачкой."""
import json, os, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "_страницы")
SETS = (("d0rj/gsm8k-ru", "default", "ru"), ("openai/gsm8k", "main", "en"))

def page(ds, cfg, split, off):
    p = os.path.join(PAGES, "%s_%s_%05d.json" % (ds.replace("/", "_"), split, off))
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    url = "https://datasets-server.huggingface.co/rows?dataset=%s&config=%s&split=%s&offset=%d&length=100" % (ds.replace("/", "%2F"), cfg, split, off)
    for attempt in range(10):
        try:
            d = json.load(urllib.request.urlopen(url, timeout=60))
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            time.sleep(1.0)
            return d
        except Exception as e:
            w = min(90, 5 * (attempt + 1))
            print("  повтор через %d с (%s, %s, %d): %s" % (w, ds, split, off, e), flush=True)
            time.sleep(w)
    raise SystemExit("не скачалось: %s %s %d" % (ds, split, off))

for ds, cfg, tag in SETS:
    for split in ("train", "test"):
        rows, off = [], 0
        while True:
            d = page(ds, cfg, split, off)
            got = [r["row"] for r in d["rows"]]
            rows += got; off += len(got)
            if not got or off >= d["num_rows_total"]:
                break
        with open(os.path.join(HERE, "gsm8k_%s_%s.jsonl" % (tag, split)), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({"question": r["question"], "answer": r["answer"]}, ensure_ascii=False) + "\n")
        print(ds, split, len(rows), "из", d["num_rows_total"], flush=True)
