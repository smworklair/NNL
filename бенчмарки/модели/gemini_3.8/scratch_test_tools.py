# -*- coding: utf-8 -*-
import sys
import os
import json
import urllib.request
import urllib.error

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
    {"role": "system", "content": "Ты медицинский ассистент. Если призывник называет симптом, обязательно вызови функцию search_schedule."},
    {"role": "user", "content": "У меня близорукость минус 6"}
]

body = {
    "model": "qwen/qwen3.8-27b",
    "messages": messages,
    "tools": tools,
    "tool_choice": "auto",
    "max_completion_tokens": 300,
    "temperature": 0.1
}

headers = {
    "Authorization": "Bearer " + key,
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 NNL-lab"
}

req = urllib.request.Request(base_url, data=json.dumps(body).encode("utf-8"), headers=headers)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.load(resp)
        msg = res["choices"][0]["message"]
        print("Model:", res.get("model"))
        print("Tool calls:", msg.get("tool_calls"))
        print("Content:", msg.get("content"))
        print("Usage:", res.get("usage"))
except Exception as e:
    print("Error:", type(e), e)
