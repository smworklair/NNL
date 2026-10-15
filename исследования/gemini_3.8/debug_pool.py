# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from клиент_агента import _вызов_одной_модели
from режим_агент import СИСТЕМА_АГЕНТА, ИНСТРУМЕНТЫ
from данные_кейсы import получить_выборку

case = получить_выборку(True)[0]
msgs = [
    {"role": "system", "content": СИСТЕМА_АГЕНТА},
    {"role": "user", "content": f"Призывник обратился:\n«{case['жалоба']}»"},
]

print("--- Testing openai/gpt-oss-20b ---")
r0 = _вызов_одной_модели("openai/gpt-oss-20b", msgs, ИНСТРУМЕНТЫ, "auto", 0.1, 350, 30, False)
print("Keys:", list(r0.keys()))
if "_ошибка" in r0:
    print("Error code:", r0["_ошибка"])
    print("Msg:", r0.get("сообщение")[:200])
else:
    print("Tool calls:", r0.get("tool_calls"))
    print("Content:", r0.get("content"))
