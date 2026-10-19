# -*- coding: utf-8 -*-
import sys, time, torch
from transformers import AutoTokenizer, AutoModelForCausalLM
sys.stdout.reconfigure(encoding="utf-8")

tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct", local_files_only=True)
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct", local_files_only=True, dtype=torch.float32)

messages = [
    {"role": "system", "content": "Ты — независимый юридическо-медицинский консультант по призыву. Твоя задача — выяснить реальную правду по Расписанию болезней, не поддакивать призывнику, а проверить факты и задать контрольные вопросы."},
    {"role": "user", "content": "У меня зрение -5.5 и постоянные головные боли, годен ли я?"}
]

prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tok(prompt, return_tensors="pt")

t0 = time.time()
with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=150, temperature=0.7, top_p=0.9, do_sample=True)
t1 = time.time()

resp_tokens = out[0][inputs["input_ids"].shape[1]:]
print(tok.decode(resp_tokens, skip_special_tokens=True))
print("Gen time:", round(t1 - t0, 2), "s")
