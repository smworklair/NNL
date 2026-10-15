# -*- coding: utf-8 -*-
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\NNL\диалог")
from данные_кейсы import получить_выборку
import клиент as К
import знания as З
from режим_агент import ИНСТРУМЕНТЫ, СИСТЕМА_АГЕНТА

case = получить_выборку(True)[0]
cfg = К.конфиг_провайдера("groq")
key = К.ключ_провайдера("groq")
база = З.База()
t34 = база.статьи["34"].текст_для_модели(800)

msgs = [
    {"role": "system", "content": СИСТЕМА_АГЕНТА},
    {"role": "user", "content": f"Призывник обратился:\n«{case['жалоба']}»"},
    {
        "role": "assistant",
        "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "поиск_статей", "arguments": '{"запрос":"близорукость миопия"}'}}],
    },
    {
        "role": "tool",
        "tool_call_id": "c1",
        "content": json.dumps({"найденные_статьи": [{"статья": "34", "название": "Нарушения рефракции", "вероятность": 0.99}]}, ensure_ascii=False),
    },
    {
        "role": "assistant",
        "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "читать_статью", "arguments": '{"номер_статьи":"34"}'}}],
    },
    {
        "role": "tool",
        "tool_call_id": "c2",
        "content": json.dumps({"статья": "34", "текст": t34}, ensure_ascii=False),
    },
    {
        "role": "assistant",
        "tool_calls": [{"id": "c3", "type": "function", "function": {"name": "уточнить_у_призывника", "arguments": '{"вопрос":"Чем подтверждено?"}'}}],
    },
    {
        "role": "tool",
        "tool_call_id": "c3",
        "content": json.dumps({"ответ_призывника": case["ответ_на_вопрос"], "статус_подтверждения": "Диагноз подтвержден врачом в медучреждении."}, ensure_ascii=False),
    },
]

body = {
    "model": "qwen/qwen3.8-27b",
    "messages": msgs,
    "tools": ИНСТРУМЕНТЫ,
    "max_completion_tokens": 300,
    "temperature": 0.1,
}

req = urllib.request.Request(
    cfg["base_url"].rstrip("/") + "/chat/completions",
    data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 NNL-lab",
    },
)

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
        print("SUCCESS TURN 4:", d["choices"][0]["message"])
except urllib.error.HTTPError as e:
    raw = e.read().decode("utf-8")
    print("CODE:", e.code)
    print("RAW:", raw)
