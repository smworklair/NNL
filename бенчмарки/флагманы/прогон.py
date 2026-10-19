# -*- coding: utf-8 -*-
"""Прогон флагмана через API на наборе замера. Тратит деньги с вашего ключа — сначала --пробный и --предел 1.

Каждой модели даётся одно и то же: инструкция с определениями областей, закрытый список (88 статей Расписания болезней
и 44 правовые темы из внешние/справочник.json) и пачка вопросов (по 10). Ответ — JSON. Сырые ответы кэшируются по пачкам
в сырые/<имя>/ — прерванный прогон продолжается с места остановки. Итог — ответы/<имя>.jsonl.

Ключи — только из переменных окружения (в чат и в файлы их не пишите):
  anthropic   — ANTHROPIC_API_KEY (или профиль `ant auth login`); нужен пакет anthropic;
  openai      — OPENAI_API_KEY; нужен пакет openai;
  xai         — XAI_API_KEY; пакет openai (у xAI API, совместимый с OpenAI);
  совместимый — любой API, совместимый с OpenAI: --адрес и --ключ-переменная.
Установка пакетов: pip install anthropic openai

Anthropic: структурированный ответ по схеме (output_config.format), усилие high (у claude-opus-5-5 по умолчанию medium),
подстраховка при отказе fallbacks: "default". Ответ, который выдала подстраховочная модель, засчитывается названной
модели как отказ, а не как её ответ. Выключить подстраховку: --без-подстраховки.

Примеры:
  python -I прогон.py --провайдер anthropic --модель claude-opus-5-5 --пробный
  python -I прогон.py --провайдер anthropic --модель claude-opus-5-5 --предел 1
  python -I прогон.py --провайдер anthropic --модель claude-opus-5-5
  python -I прогон.py --провайдер anthropic --модель claude-fable-5-1
  python -I прогон.py --провайдер openai --модель <флагман OpenAI из их документации> --имя gpt
  python -I прогон.py --провайдер xai --модель <флагман xAI из их документации> --имя grok"""
import argparse
import datetime
import json
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from замер_общее import (ОТВЕТЫ, СЫРЫЕ, СХЕМА, write_jl, набор, пачки, разобрать, системный_текст,  # noqa: E402
                   текст_вопросов, sha256_text)

# $ за 1 млн токенов: вход, выход, чтение кэша, запись кэша. Оценка по прайсу Anthropic на 2026-10-06 (запись кэша — 1,25 × вход).
ЦЕНЫ = {"claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
        "claude-fable-5-1": (10.0, 50.0, 0.25, 12.5),
        "claude-sonnet-5-5": (2.0, 10.0, 0.20, 2.5)}
АДРЕСА = {"openai": (None, "OPENAI_API_KEY"), "xai": ("https://api.x.ai/v1", "XAI_API_KEY")}


class Anthropic:
    def __init__(self, a):
        import anthropic
        self.lib = anthropic
        self.client = anthropic.Anthropic(max_retries=6)
        self.a = a

    def __call__(self, system, user):
        kw = dict(model=self.a.модель, max_tokens=16000,
                  system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                  messages=[{"role": "user", "content": user}],
                  output_config={"effort": self.a.усилие or "high",
                                 "format": {"type": "json_schema", "schema": СХЕМА}})
        if self.a.без_подстраховки:
            resp = self.client.messages.create(**kw)
        else:
            resp = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        iters = getattr(resp.usage, "iterations", None) or []
        u = resp.usage
        return {"текст": text, "модель_ответила": resp.model, "stop_reason": resp.stop_reason,
                "подстраховка": any(getattr(it, "type", "") == "fallback_message" for it in iters),
                "usage": {"вход": u.input_tokens, "выход": u.output_tokens,
                          "кэш_чтение": getattr(u, "cache_read_input_tokens", 0) or 0,
                          "кэш_запись": getattr(u, "cache_creation_input_tokens", 0) or 0}}

    def fatal(self, e):
        return isinstance(e, (self.lib.BadRequestError, self.lib.AuthenticationError, self.lib.PermissionDeniedError,
                              self.lib.NotFoundError))


class OpenAICompatible:
    def __init__(self, a):
        import openai
        self.lib = openai
        base, keyvar = АДРЕСА.get(a.провайдер, (a.адрес, a.ключ_переменная))
        if not keyvar or not os.environ.get(keyvar):
            sys.exit("нет ключа: задайте переменную окружения %s" % keyvar)
        self.client = openai.OpenAI(api_key=os.environ[keyvar], base_url=base, max_retries=6)
        self.a = a

    def __call__(self, system, user):
        kw = {"reasoning_effort": self.a.усилие} if self.a.усилие else {}
        resp = self.client.chat.completions.create(
            model=self.a.модель, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **kw)
        ch = resp.choices[0]
        u = resp.usage
        return {"текст": ch.message.content or "", "модель_ответила": resp.model, "stop_reason": ch.finish_reason,
                "подстраховка": False,
                "usage": {"вход": getattr(u, "prompt_tokens", 0) or 0, "выход": getattr(u, "completion_tokens", 0) or 0}}

    def fatal(self, e):
        return isinstance(e, (self.lib.BadRequestError, self.lib.AuthenticationError, self.lib.PermissionDeniedError,
                              self.lib.NotFoundError))


def args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--провайдер", required=True, choices=["anthropic", "openai", "xai", "совместимый"])
    p.add_argument("--модель", required=True)
    p.add_argument("--имя", help="имя системы в таблице (по умолчанию — имя модели)")
    p.add_argument("--усилие", help="anthropic: low|medium|high|xhigh|max (по умолчанию high); другие — reasoning_effort, если задан")
    p.add_argument("--пачка", type=int, default=10, help="вопросов в одном запросе")
    p.add_argument("--предел", type=int, help="сколько пачек прогнать (для пробы)")
    p.add_argument("--адрес", help="для «совместимый»: base_url API")
    p.add_argument("--ключ-переменная", dest="ключ_переменная", help="для «совместимый»: имя переменной окружения с ключом")
    p.add_argument("--без-подстраховки", dest="без_подстраховки", action="store_true")
    p.add_argument("--пробный", action="store_true", help="ничего не отправлять: показать первый запрос и объём")
    a = p.parse_args()
    a.имя = a.имя or re.sub(r"[^\w.-]+", "_", a.модель)
    return a


def main():
    a = args()
    rows = набор()
    system = системный_текст()
    sha = sha256_text(system + json.dumps(СХЕМА, ensure_ascii=False, sort_keys=True))
    batches = пачки(rows, a.пачка)
    if a.предел:
        batches = batches[:a.предел]
    if a.пробный:
        print(system)
        print("\n=====\n" + текст_вопросов(batches[0]))
        print("\n=====\nпачек %d, вопросов %d; инструкция и список %d знаков (одинаковы во всех запросах, у Anthropic кэшируются), "
              "вопросы первой пачки %d знаков" % (len(batches), sum(map(len, batches)), len(system), len(текст_вопросов(batches[0]))))
        return
    call = Anthropic(a) if a.провайдер == "anthropic" else OpenAICompatible(a)
    raw = os.path.join(СЫРЫЕ, a.имя)
    os.makedirs(raw, exist_ok=True)
    for k, b in enumerate(batches, 1):
        keys = [r["ключ"] for r in b]
        path = os.path.join(raw, "пачка_%03d.json" % k)
        if os.path.exists(path):
            rec = json.load(open(path, encoding="utf-8"))
            if rec.get("ключи") == keys and rec.get("запрос_sha") == sha and rec.get("ок"):
                continue
        user = текст_вопросов(b)
        res, ok = None, False
        for attempt in (1, 2):
            try:
                res = call(system, user)
            except Exception as e:  # noqa: BLE001
                if call.fatal(e):
                    sys.exit("запрос отклонён, прогон остановлен: %s" % e)
                sys.exit("сеть или сервер не ответили после повторов, прогон остановлен (сделанное сохранено): %s" % e)
            ok = len(разобрать(res["текст"], len(b))) == len(b) and res["stop_reason"] not in ("max_tokens", "length")
            if ok or res["stop_reason"] == "refusal":
                break
        rec = {"ключи": keys, "запрос_sha": sha, "провайдер": a.провайдер, "модель": a.модель,
               "усилие": a.усилие or ("high" if a.провайдер == "anthropic" else None), "пачка": a.пачка,
               "когда": datetime.datetime.now().isoformat(timespec="seconds"), "ок": ok, **res}
        if res["stop_reason"] == "refusal" or res["подстраховка"]:
            # отказ на пачку мог вызвать один вопрос — переспросить по одному, чтобы не терять остальные
            rec["по_одному"] = []
            for r in b:
                try:
                    one = call(system, текст_вопросов([r]))
                except Exception as e:  # noqa: BLE001
                    sys.exit("прогон остановлен на переспросе по одному: %s" % e)
                rec["по_одному"].append({"ключ": r["ключ"], **one})
            rec["ок"] = True
        json.dump(rec, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("пачка %d/%d: %s, ответила %s%s" % (k, len(batches), "ок" if ok else "НЕ РАЗОБРАНО (%s)" % res["stop_reason"],
                                                  res["модель_ответила"], ", ПОДСТРАХОВКА" if res["подстраховка"] else ""), flush=True)
    собрать(a, batches, raw, sha)


def собрать(a, batches, raw, sha):
    out, usage, served = [], {}, set()
    for k, b in enumerate(batches, 1):
        path = os.path.join(raw, "пачка_%03d.json" % k)
        rec = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
        if rec is None or rec.get("запрос_sha") != sha:
            out += [{"ключ": r["ключ"], "сбой": "нет ответа"} for r in b]
            continue
        for part in [rec] + rec.get("по_одному", []):
            for x, v in part.get("usage", {}).items():
                usage[x] = usage.get(x, 0) + v
            served.add(part.get("модель_ответила"))
        if "по_одному" in rec:
            for one in rec["по_одному"]:
                p1 = разобрать(one.get("текст"), 1)
                if one.get("stop_reason") == "refusal" or one.get("подстраховка"):
                    out.append({"ключ": one["ключ"], "сбой": "отказ модели", "модель_ответила": one.get("модель_ответила")})
                elif 1 in p1:
                    area, idv, conf = p1[1]
                    out.append({"ключ": one["ключ"], "область": area, "id": idv, "уверенность": conf,
                                "модель_ответила": one.get("модель_ответила")})
                else:
                    out.append({"ключ": one["ключ"], "сбой": "нет ответа"})
            continue
        parsed = разобрать(rec.get("текст"), len(b))
        for n, r in enumerate(b, 1):
            if n in parsed:
                area, idv, conf = parsed[n]
                out.append({"ключ": r["ключ"], "область": area, "id": idv, "уверенность": conf,
                            "модель_ответила": rec.get("модель_ответила")})
            else:
                out.append({"ключ": r["ключ"], "сбой": "нет ответа"})
    write_jl(os.path.join(ОТВЕТЫ, a.имя + ".jsonl"), out)
    print("итог: %s — %d ответов, сбоев %d; отвечали модели: %s" % (
        a.имя, sum("сбой" not in o for o in out), sum("сбой" in o for o in out), ", ".join(sorted(map(str, served)))))
    print("токены:", usage)
    price = ЦЕНЫ.get(a.модель)
    if price and usage:
        cost = (usage.get("вход", 0) * price[0] + usage.get("выход", 0) * price[1] +
                usage.get("кэш_чтение", 0) * price[2] + usage.get("кэш_запись", 0) * price[3]) / 1e6
        print("оценка стоимости: $%.2f (по прайсу на 2026-10-06; точную сумму смотрите в консоли провайдера)" % cost)


if __name__ == "__main__":
    main()
