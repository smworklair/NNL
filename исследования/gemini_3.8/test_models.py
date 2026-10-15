# -*- coding: utf-8 -*-
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\ЯДРО-ОПЫТ\NNL\диалог")
import клиент as К

cfg = К.конфиг_провайдера("groq")
key = К.ключ_провайдера("groq")

candidate_models = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "qwen-2.5-32b",
    "qwen/qwen-2.5-32b",
]

for mod in candidate_models:
    body = {
        "model": mod,
        "messages": [{"role": "user", "content": "hi"}],
        "max_completion_tokens": 10,
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
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.load(r)
            print(f"[{mod}]: SUCCESS -> {res['choices'][0]['message']['content'][:30]}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            msg = json.loads(raw)["error"]["message"]
        except Exception:
            msg = raw[:100]
        print(f"[{mod}]: ERROR {e.code} -> {msg[:80]}")
    except Exception as e:
        print(f"[{mod}]: OTHER ERROR -> {e}")
