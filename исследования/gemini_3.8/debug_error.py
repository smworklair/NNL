# -*- coding: utf-8 -*-
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\NNL\диалог")
from данные_кейсы import получить_выборку
import клиент as К
from режим_агент import ИНСТРУМЕНТЫ, СИСТЕМА_АГЕНТА

case = получить_выборку(True)[0]
cfg = К.конфиг_провайдера("groq")
key = К.ключ_провайдера("groq")

body = {
    "model": "qwen/qwen3.8-27b",
    "messages": [
        {"role": "system", "content": СИСТЕМА_АГЕНТА},
        {"role": "user", "content": f"Призывник обратился с сообщением:\n«{case['жалоба']}»\nПроведи расследование через инструменты и дай ответ."},
    ],
    "tools": ИНСТРУМЕНТЫ,
    "max_completion_tokens": 350,
}

req = urllib.request.Request(
    cfg["base_url"].rstrip("/") + "/chat/completions",
    data=json.dumps(body).encode("utf-8"),
    headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 NNL-lab",
    },
)

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
        print("SUCCESS:", d["choices"][0]["message"])
except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code)
    print("HEADERS:", dict(e.headers))
    print("BODY:", e.read().decode("utf-8"))
except Exception as e:
    print("OTHER ERROR:", type(e), e)
