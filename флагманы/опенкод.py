# -*- coding: utf-8 -*-
"""Прогон флагмана через OpenCode (`opencode run`) — любой моделью из `opencode models`, без своих ключей API.

Каждая пачка (10 вопросов) — отдельная новая сессия OpenCode: пачки не влияют друг на друга. Запрос тот же, что у прогон.py
и у ручного режима: инструкция, закрытый список (88 статей, 44 темы) и вопросы. Модель работает агентом «zamer»
из опенкод_папка/opencode.json: у него запрещены все инструменты (чтение файлов, bash, веб) — модель отвечает сама и
не может заглянуть в эталон. Папка запуска пустая, кроме этого файла настроек.
Сырые ответы — сырые/<имя>/пачка_NNN.json (прерванный прогон продолжается с места остановки), итог — ответы/<имя>.jsonl.

Бесплатные модели opencode/… через `opencode run` не работают (ответ сервера: «free tier can only be used from within
OpenCode»), нужны модели подписки, например opencode-go/…. Посмотреть список: opencode models

Примеры:
  python -I опенкод.py --модель opencode-go/grok-4.7 --предел 1          — проба: одна пачка
  python -I опенкод.py --модель opencode-go/grok-4.7                     — все 600 вопросов (60 пачек)
  python -I опенкод.py --модель opencode-go/gpt-6-luna --вариант high    — с повышенным усилием рассуждения, если модель его знает
  python -I опенкод.py --модель opencode-go/kimi-k3 --выборка            — только 60 вопросов ручной выборки
  python -I опенкод.py --модель opencode-go/grok-4.7 --потоков 3         — три пачки одновременно"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from замер_общее import (ОТВЕТЫ, ROOT, СЫРЫЕ, write_jl, набор, пачки, разобрать, системный_текст,  # noqa: E402
                         текст_вопросов, sha256_text)

ПАПКА = os.path.join(ROOT, "опенкод_папка")
АГЕНТ = "zamer"
ВЫБОРКА = os.path.join(ROOT, "ручной", "выборка.json")
СТОП = threading.Event()


def opencode_exe(given):
    if given:
        return given
    w = shutil.which("opencode")
    if not w:
        sys.exit("opencode не найден в PATH")
    exe = os.path.join(os.path.dirname(w), "node_modules", "opencode-ai", "bin", "opencode.exe")
    return exe if os.path.exists(exe) else w


def запустить(a, exe, prompt):
    """Один `opencode run` → (текст ответа, инструменты, ошибки, шаги, код выхода)."""
    cmd = [exe, "run", prompt, "--dir", ПАПКА, "--agent", АГЕНТ, "-m", a.модель, "--format", "json"]
    if a.вариант:
        cmd += ["--variant", a.вариант]
    try:
        p = subprocess.run(cmd, cwd=ПАПКА, capture_output=True, timeout=a.таймаут)
        out, code = p.stdout.decode("utf-8", "replace"), p.returncode
        err_text = p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return "", [], ["таймаут %d с" % a.таймаут], [], None
    texts, tools, errors, steps = [], [], [], []
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        part = e.get("part") or {}
        if e.get("type") == "text":
            texts.append(part.get("text") or "")
        elif e.get("type") == "tool_use":
            tools.append(part.get("tool"))
        elif e.get("type") == "step_finish":
            steps.append({k: part.get(k) for k in ("tokens", "cost") if k in part})
        elif e.get("type") == "error":
            err = e.get("error") or {}
            data = err.get("data") or {}
            errors.append("%s: %s (код %s)" % (err.get("name"), data.get("message"), data.get("statusCode")))
    if code and not errors:
        errors.append("код выхода %s: %s" % (code, err_text.strip()[:300]))
    return "\n".join(texts), tools, errors, steps, code


def роковая(errors):
    return any(re.search(r"код (401|403|404)\)|not found|FreeTierError|free tier", e, re.I) for e in errors)


def одна_пачка(a, exe, k, b, sha, raw):
    path = os.path.join(raw, "пачка_%03d.json" % k)
    keys = [r["ключ"] for r in b]
    if os.path.exists(path):
        rec = json.load(open(path, encoding="utf-8"))
        if rec.get("ключи") == keys and rec.get("запрос_sha") == sha and rec.get("ок"):
            return k, rec, True
    if СТОП.is_set():
        return k, None, True
    prompt = системный_текст() + "\n\n" + текст_вопросов(b)
    rec = None
    for attempt in (1, 2):
        text, tools, errors, steps, code = запустить(a, exe, prompt)
        ok = not errors and not tools and len(разобрать(text, len(b))) == len(b)
        rec = {"ключи": keys, "запрос_sha": sha, "через": "opencode run", "модель": a.модель, "вариант": a.вариант,
               "агент": АГЕНТ, "когда": datetime.datetime.now().isoformat(timespec="seconds"), "ок": ok, "текст": text,
               "инструменты": tools, "ошибки": errors, "шаги": steps, "код_выхода": code, "попытка": attempt}
        if ok or роковая(errors):
            break
    if роковая(rec["ошибки"]):
        СТОП.set()
    json.dump(rec, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return k, rec, False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--модель", required=True, help="provider/model из `opencode models`")
    p.add_argument("--имя", help="имя системы в таблице (по умолчанию — имя модели)")
    p.add_argument("--вариант", help="--variant для opencode: усилие рассуждения (high, max …), если модель его поддерживает")
    p.add_argument("--пачка", type=int, default=10)
    p.add_argument("--предел", type=int, help="сколько пачек прогнать (для пробы)")
    p.add_argument("--выборка", action="store_true", help="только 60 вопросов ручной выборки (ручной/выборка.json)")
    p.add_argument("--потоков", type=int, default=1, help="сколько пачек гнать одновременно (1–4)")
    p.add_argument("--таймаут", type=int, default=900, help="секунд на одну пачку")
    p.add_argument("--opencode", help="путь к opencode.exe, если не находится сам")
    a = p.parse_args()
    a.имя = a.имя or "oc_" + re.sub(r"[^\w.-]+", "_", a.модель)
    if not os.path.exists(os.path.join(ПАПКА, "opencode.json")):
        sys.exit("нет %s — настройка агента без инструментов" % os.path.join(ПАПКА, "opencode.json"))
    exe = opencode_exe(a.opencode)
    rows = набор()
    if a.выборка:
        sel = json.load(open(ВЫБОРКА, encoding="utf-8"))
        by_key = {r["ключ"]: r for r in rows}
        batches = [[by_key[k] for k in b] for b in sel["пачки"]]
    else:
        batches = пачки(rows, a.пачка)
    if a.предел:
        batches = batches[:a.предел]
    sha = sha256_text(системный_текст())
    raw = os.path.join(СЫРЫЕ, a.имя)
    os.makedirs(raw, exist_ok=True)
    print("модель %s, пачек %d, потоков %d; сырые ответы — %s" % (a.модель, len(batches), a.потоков, raw), flush=True)
    stop = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(4, a.потоков))) as pool:
        futs = [pool.submit(одна_пачка, a, exe, k, b, sha, raw) for k, b in enumerate(batches, 1)]
        for f in concurrent.futures.as_completed(futs):
            if f.cancelled():
                continue
            k, rec, cached = f.result()
            if cached:
                continue
            state = "ок" if rec["ок"] else "НЕ РАЗОБРАНО"
            extra = ("; инструменты: %s" % rec["инструменты"] if rec["инструменты"] else "") + \
                    ("; ошибки: %s" % rec["ошибки"] if rec["ошибки"] else "")
            print("пачка %d/%d: %s%s" % (k, len(batches), state, extra), flush=True)
            if роковая(rec["ошибки"]) and not stop:
                stop = True
                СТОП.set()
                print("модель недоступна — остальные пачки отменяются", flush=True)
                for g in futs:
                    g.cancel()
    собрать(a, batches, raw, sha)


def собрать(a, batches, raw, sha):
    out, tokens = [], {}
    for k, b in enumerate(batches, 1):
        path = os.path.join(raw, "пачка_%03d.json" % k)
        rec = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
        if rec is None or rec.get("запрос_sha") != sha or rec.get("инструменты"):
            out += [{"ключ": r["ключ"], "сбой": "нет ответа"} for r in b]
            continue
        for s in rec.get("шаги") or []:
            t = s.get("tokens") or {}
            for x in ("input", "output", "reasoning"):
                tokens[x] = tokens.get(x, 0) + (t.get(x) or 0)
            tokens["cost"] = tokens.get("cost", 0) + (s.get("cost") or 0)
        parsed = разобрать(rec.get("текст"), len(b))
        for n, r in enumerate(b, 1):
            if n in parsed:
                area, idv, conf = parsed[n]
                out.append({"ключ": r["ключ"], "область": area, "id": idv, "уверенность": conf})
            else:
                out.append({"ключ": r["ключ"], "сбой": "нет ответа"})
    write_jl(os.path.join(ОТВЕТЫ, a.имя + ".jsonl"), out)
    print("итог: %s — %d ответов, сбоев %d; токены и стоимость по данным OpenCode: %s" % (
        a.имя, sum("сбой" not in o for o in out), sum("сбой" in o for o in out), tokens or "нет данных"))
    print("дальше: python -I оценка.py")


if __name__ == "__main__":
    main()
