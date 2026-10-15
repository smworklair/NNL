# -*- coding: utf-8 -*-
"""Клиент для автономного агента с поддержкой OpenAI-совместимых инструментов (tools)
и пула моделей (модель1|модель2), как в NNL/диалог.
Работает через стандартную библиотеку urllib, использует ключи и настройки из NNL/диалог.
Никакие ключи не выводятся в лог и не печатаются на экран.
Ведёт кэш вызовов в кэш_агента.jsonl и аккуратно учитывает токены, вызовы и задержки.
При 429 переключается на следующую модель в пуле или ждёт точное время.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\NNL\диалог")
import клиент as NNL_К

ПАПКА = os.path.dirname(os.path.abspath(__file__))
КЭШ_ФАЙЛ = os.path.join(ПАПКА, "кэш_агента.jsonl")

СЧЁТЧИК = {
    "вызовов_всего": 0,
    "вызовов_сеть": 0,
    "из_кэша": 0,
    "ошибок": 0,
    "токены_вход": 0,
    "токены_выход": 0,
    "мс_всего": 0,
    "повторов_429": 0,
}

_кэш = None


def _загрузить_кэш():
    global _кэш
    if _кэш is None:
        _кэш = {}
        if os.path.exists(КЭШ_ФАЙЛ):
            with open(КЭШ_ФАЙЛ, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        _кэш[r["ключ"]] = r["ответ"]
                    except Exception:
                        pass
    return _кэш


def _записать_кэш(ключ, ответ):
    with open(КЭШ_ФАЙЛ, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ключ": ключ, "ответ": ответ}, ensure_ascii=False) + "\n")
    if _кэш is not None:
        _кэш[ключ] = ответ


def сбросить_счётчик():
    global СЧЁТЧИК
    for k in СЧЁТЧИК:
        СЧЁТЧИК[k] = 0


def получить_статистику():
    return dict(СЧЁТЧИК)


def _хеш_запроса(модель, сообщения, tools, tool_choice, температура, макс_токенов):
    данные = [
        модель,
        сообщения,
        tools,
        tool_choice,
        температура,
        макс_токенов,
    ]
    raw = json.dumps(данные, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _вызов_одной_модели(
    модель,
    сообщения,
    tools,
    tool_choice,
    температура,
    макс_токенов,
    таймаут,
    кэш,
):
    СЧЁТЧИК["вызовов_всего"] += 1
    хеш = _хеш_запроса(модель, сообщения, tools, tool_choice, температура, макс_токенов)

    if кэш:
        к = _загрузить_кэш().get(хеш)
        if к is not None:
            СЧЁТЧИК["из_кэша"] += 1
            res = dict(к)
            res["из_кэша"] = True
            res["мс"] = 0
            return res

    cfg = NNL_К.конфиг_провайдера("groq")
    key = NNL_К.ключ_провайдера("groq")
    if not key:
        raise RuntimeError("Отсутствует ключ API для Groq")

    base_url = cfg["base_url"].rstrip("/") + "/chat/completions"

    тело = {
        "model": модель,
        "messages": сообщения,
        "temperature": температура,
        "max_completion_tokens": макс_токенов,
    }
    if tools:
        тело["tools"] = tools
        if tool_choice:
            тело["tool_choice"] = tool_choice

    данные_байты = json.dumps(тело, ensure_ascii=False).encode("utf-8")
    заголовки = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 NNL-lab",
    }

    t0 = time.time()
    req = urllib.request.Request(base_url, data=данные_байты, headers=заголовки)

    try:
        with urllib.request.urlopen(req, timeout=таймаут) as resp:
            res_json = json.load(resp)

        мс = int((time.time() - t0) * 1000)
        choice = res_json["choices"][0]
        msg = choice["message"]
        usage = res_json.get("usage", {})
        т_вх = usage.get("prompt_tokens", 0)
        т_вых = usage.get("completion_tokens", 0)

        СЧЁТЧИК["вызовов_сеть"] += 1
        СЧЁТЧИК["токены_вход"] += т_вх
        СЧЁТЧИК["токены_выход"] += т_вых
        СЧЁТЧИК["мс_всего"] += мс

        результат = {
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": msg.get("tool_calls"),
            "usage": {
                "prompt_tokens": т_вх,
                "completion_tokens": т_вых,
                "total_tokens": usage.get("total_tokens", т_вх + т_вых),
            },
            "мс": мс,
            "из_кэша": False,
            "повторов_429": 0,
            "модель": модель,
        }

        if кэш:
            _записать_кэш(хеш, результат)

        time.sleep(1.0)
        return результат

    except urllib.error.HTTPError as e:
        сырое = ""
        try:
            сырое = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass

        if e.code == 429:
            ждать = 10.0
            m_min = re.search(r"try again in (\d+)m([\d.]+)s", сырое, re.I)
            if m_min:
                try:
                    ждать = float(m_min.group(1)) * 60 + float(m_min.group(2)) + 2.0
                except Exception:
                    ждать = 65.0
            else:
                m_sec = re.search(r"try again in ([\d.]+)s", сырое, re.I) or re.search(r"retry in ([\d.]+)s", сырое, re.I)
                if m_sec:
                    try:
                        ждать = float(m_sec.group(1)) + 2.0
                    except Exception:
                        ждать = 15.0
                else:
                    h = e.headers.get("retry-after")
                    if h:
                        try:
                            ждать = float(h.split()[0]) + 2.0
                        except Exception:
                            ждать = 15.0
            ждать = min(max(ждать, 2.0), 120.0)
            return {"_ошибка": 429, "ждать": ждать, "сообщение": сырое}

        if e.code == 400 and "tool_use_failed" in сырое:
            return {"_ошибка": 400, "ждать": 1.0, "сообщение": сырое}

        СЧЁТЧИК["ошибок"] += 1
        raise RuntimeError(f"HTTP ошибка {e.code}: {сырое[:200]}") from e


def вызов_модели(
    модель="openai/gpt-oss-120b|qwen/qwen3.8-27b",
    сообщения=None,
    tools=None,
    tool_choice="auto",
    температура=0.1,
    макс_токенов=350,
    таймаут=60,
    кэш=True,
):
    """Вызов языковой модели через Groq API с поддержкой пула моделей (разделитель '|')."""
    if сообщения is None:
        сообщения = []

    список_моделей = [m.strip() for m in str(модель).split("|") if m.strip()]

    for раунд in range(10):
        минимальное_ожидание = 120.0
        были_лимиты = False

        for м in список_моделей:
            рез = _вызов_одной_модели(
                модель=м,
                сообщения=сообщения,
                tools=tools,
                tool_choice=tool_choice,
                температура=температура,
                макс_токенов=макс_токенов,
                таймаут=таймаут,
                кэш=кэш,
            )

            if isinstance(рез, dict) and "_ошибка" in рез:
                код = рез["_ошибка"]
                if код == 429:
                    были_лимиты = True
                    СЧЁТЧИК["повторов_429"] += 1
                    минимальное_ожидание = min(минимальное_ожидание, рез.get("ждать", 10.0))
                    continue
                elif код == 400:
                    # tool_use_failed: переключаемся на следующую модель в пуле
                    continue
            else:
                return рез

        if были_лимиты:
            time.sleep(минимальное_ожидание)
        else:
            time.sleep(2.0)

    raise RuntimeError(f"Лимиты всех моделей пула исчерпаны ({модель})")
