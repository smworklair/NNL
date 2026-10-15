# -*- coding: utf-8 -*-
import sys
import os
import json
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\NNL\диалог")
import клиент as К

cfg = К.конфиг_провайдера("groq")
key = К.ключ_провайдера("groq")
base_url = cfg["base_url"].rstrip("/") + "/chat/completions"

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_schedule",
            "description": "Поиск статьи в Расписании болезней",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Симптом или диагноз"}
                },
                "required": ["query"]
            }
        }
    }
]

messages = [
    {"role": "system", "content": "Ты агент-исследователь NNL. Перед любым ответом призывнику ты ОБЯЗАН вызвать функцию search_schedule для поиска официальной статьи Расписания болезней."},
    {"role": "user", "content": "У меня близорукость минус 6.25 дптр"}
]

def call_groq(msgs, tools=None):
    body = {
        "model": "qwen/qwen3.8-27b",
        "messages": msgs,
        "max_completion_tokens": 400,
        "temperature": 0.1
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    headers = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 NNL-lab"
    }
    req = urllib.request.Request(base_url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.load(resp)
        return res["choices"][0]["message"]

msg1 = call_groq(messages, tools)
print("Turn 1 message:", msg1)
if msg1.get("tool_calls"):
    messages.append(msg1)
    tc = msg1["tool_calls"][0]
    messages.append({
        "role": "tool",
        "tool_call_id": tc["id"],
        "content": json.dumps({"статьи": [{"ид": "34", "название": "Нарушения рефракции и аккомодации", "порог": "более 6,0 дптр"}]}, ensure_ascii=False)
    })
    msg2 = call_groq(messages, tools)
    print("Turn 2 message:", msg2)
