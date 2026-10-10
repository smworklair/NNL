# -*- coding: utf-8 -*-
"""Потоковый фильтр архива Ответов Mail.ru (huggingface.co/datasets/its5Q/otvetmailru, CC0, 52 куска по 2,5 млн вопросов).
Куски не сохраняются: скачивание → распаковка zstd → отбор → запись. На диске остаётся только отобранное:
  армия.jsonl     — категория «Военная служба» (law_army): вопрос, пояснение, ответы (текст, оценка), лучший ответ;
  ключи.jsonl     — вопросы других категорий со словами про призыв/военкомат/армию (только вопрос и пояснение);
  право.jsonl     — остальные юридические категории (law_*), только вопрос и пояснение;
  болезни.jsonl   — illness, kidhealth, health (только вопрос и пояснение);
  фон.jsonl       — 0,5 % всех прочих вопросов (по хешу qid), только вопрос и пояснение.
Готовый кусок отмечается файлом готово/<кусок>. Запуск: python фильтр.py [процессов=4]"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from multiprocessing import Pool

import zstandard

ROOT = os.path.dirname(os.path.abspath(__file__))
URL = "https://huggingface.co/datasets/its5Q/otvetmailru/resolve/main/dataset.jsonl.%s.zst"
CHUNKS = [a + b for a in "ab" for b in "abcdefghijklmnopqrstuvwxyz"]
HEALTH = {"illness", "kidhealth", "health"}
KEYS = re.compile(r"военкомат|призыв|призов|в арми|армию|армии|армейск|повестк|отсрочк|военн\w* билет|военник|приписн|медкомисси|"
                  r"срочн\w* служб|годност|комисси\w* военкомат|ввк\b|откос|закос", re.I)
CAT = re.compile(rb'"category":\{"urlname":"([^"]*)"')
DEC = json.JSONDecoder()


class Resumable:
    """Чтение файла по HTTP с докачкой: сервер рвёт долгое соединение (~5 мин) без ошибки — продолжаем с того же байта (Range)."""

    def __init__(self, url):
        self.url, self.pos, self.total, self.resp, self.reopens = url, 0, None, None, 0
        self._open()

    def _open(self):
        for attempt in range(8):
            try:
                req = urllib.request.Request(self.url, headers={"User-Agent": "nnl-filter/1.0", "Range": "bytes=%d-" % self.pos})
                self.resp = urllib.request.urlopen(req, timeout=120)
                cr = self.resp.headers.get("Content-Range")
                if self.total is None:
                    self.total = int(cr.split("/")[1]) if cr else int(self.resp.headers.get("Content-Length"))
                if self.pos and self.resp.status != 206:
                    raise IOError("сервер не поддержал докачку")
                return
            except Exception:
                time.sleep(10 * (attempt + 1))
        raise IOError("не удалось открыть %s с байта %d" % (self.url, self.pos))

    def read(self, n=-1):
        while True:
            try:
                data = self.resp.read(n if n and n > 0 else 1 << 20)
            except Exception:
                data = b""
            if data:
                self.pos += len(data)
                return data
            if self.pos >= self.total:
                return b""
            self.reopens += 1
            self.resp.close()
            self._open()


def unthrottle():
    """Windows EcoQoS душит фоновые процессы (~5x медленнее) — снимаем для своего процесса."""
    try:
        import ctypes

        class S(ctypes.Structure):
            _fields_ = [("Version", ctypes.c_ulong), ("ControlMask", ctypes.c_ulong), ("StateMask", ctypes.c_ulong)]
        s = S(1, 1, 0)
        k = ctypes.windll.kernel32
        k.SetProcessInformation(k.GetCurrentProcess(), 4, ctypes.byref(s), ctypes.sizeof(s))
    except Exception:
        pass


def field(line, name):
    i = line.find('"%s":"' % name)
    if i < 0:
        return ""
    try:
        return DEC.raw_decode(line, i + len(name) + 3)[0]
    except ValueError:
        return ""


def clean_desc(d):
    """Пустое пояснение сайт заполняет заглушкой «Пользователь X задал вопрос в категории Y» — убираем."""
    return "" if d.startswith("Пользователь ") and "задал вопрос в категории" in d[:300] else d


def keep_fon(qid):
    return int(hashlib.md5(qid.encode()).hexdigest()[:8], 16) % 200 == 0


def process(chunk):
    unthrottle()
    done = os.path.join(ROOT, "готово", chunk)
    if os.path.exists(done):
        return chunk, "уже"
    out_dir = os.path.join(ROOT, "куски", chunk)
    os.makedirs(out_dir, exist_ok=True)
    for attempt in range(4):
        try:
            t0 = time.time()
            outs = {n: open(os.path.join(out_dir, n + ".jsonl"), "w", encoding="utf-8") for n in ("армия", "ключи", "право", "болезни", "фон")}
            cnt = dict.fromkeys(outs, 0)
            n = 0
            resp = Resumable(URL % chunk)
            rd = zstandard.ZstdDecompressor(max_window_size=2 ** 31).stream_reader(resp, read_across_frames=True)
            tail = b""
            while True:
                block = rd.read(1 << 22)
                if not block:
                    break
                lines = (tail + block).split(b"\n")
                tail = lines.pop()
                for raw in lines:
                    n += 1
                    m = CAT.search(raw, 0, 4000) or CAT.search(raw)
                    cat = m.group(1).decode() if m else ""
                    line = None
                    if cat == "law_army":
                        try:
                            o = json.loads(raw)
                        except ValueError:
                            continue
                        ans = [{"t": a.get("atext", ""), "r": a.get("rating", "0")} for a in (o.get("answers") or []) if isinstance(a, dict)]
                        best = o.get("best") if isinstance(o.get("best"), dict) else {}
                        rec = {"qid": o.get("qid"), "t": o.get("created_at"), "кат": cat, "вопрос": o.get("qtext", ""),
                               "пояснение": clean_desc(o.get("description", "") or ""), "лучший": best.get("atext", ""), "ответы": ans}
                        outs["армия"].write(json.dumps(rec, ensure_ascii=False) + "\n")
                        cnt["армия"] += 1
                        continue
                    line = raw.decode("utf-8", "replace")
                    q, d, qid = field(line, "qtext"), clean_desc(field(line, "description")), field(line, "qid")
                    rec = {"qid": qid, "кат": cat, "вопрос": q, "пояснение": d}
                    s = json.dumps(rec, ensure_ascii=False) + "\n"
                    if KEYS.search(q) or KEYS.search(d[:500]):
                        outs["ключи"].write(s)
                        cnt["ключи"] += 1
                    elif cat.startswith("law"):
                        outs["право"].write(s)
                        cnt["право"] += 1
                    elif cat in HEALTH:
                        outs["болезни"].write(s)
                        cnt["болезни"] += 1
                    elif keep_fon(qid):
                        outs["фон"].write(s)
                        cnt["фон"] += 1
            for f in outs.values():
                f.close()
            os.makedirs(os.path.dirname(done), exist_ok=True)
            if resp.pos < resp.total:
                raise IOError("кусок прочитан не полностью: %d из %d байт" % (resp.pos, resp.total))
            json.dump({"записей": n, "отобрано": cnt, "сек": round(time.time() - t0), "байт": resp.total, "докачек": resp.reopens},
                      open(done, "w", encoding="utf-8"), ensure_ascii=False)
            return chunk, "ок %d %s %ds докачек %d" % (n, cnt, time.time() - t0, resp.reopens)
        except Exception as e:
            for f in outs.values():
                f.close()
            err = repr(e)
            time.sleep(30 * (attempt + 1))
    return chunk, "ошибка " + err


if __name__ == "__main__":
    unthrottle()
    procs = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    with Pool(procs) as p:
        for chunk, msg in p.imap_unordered(process, CHUNKS):
            print(time.strftime("%H:%M:%S"), chunk, msg, flush=True)
