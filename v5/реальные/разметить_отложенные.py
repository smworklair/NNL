# -*- coding: utf-8 -*-
"""Отложенный набор: 120 случайных вопросов calm_topic (Ответы Mail.ru), которых не было в первой разметке.
Размечен учителем (Claude) ДО починки заявок и правила спора; на нём починка не настраивается."""
import hashlib, json, sys
sys.stdout.reconfigure(encoding="utf-8")
S = "fz53_otsrochka_semeynye_obstoyatelstva"; O = "fz53_osvobozhdenie_ot_prizyva"
H = {2: [], 33: ["22"], 36: [], 63: ["45"], 69: ["57", "59"], 94: ["62"], 95: ["17"], 98: ["10"], 100: ["52"], 102: ["1", "59"], 112: ["49"], 115: ["2", "3"]}
P = {0: ["kak_prohodit_medkomissiya"], 13: ["kak_prohodit_medkomissiya"], 15: [], 17: ["pp565_pereosvidetelstvovanie_kategoriya_v"], 19: ["pp663_raspredelenie_otpravka"],
     23: [], 34: [], 42: ["kategorii_godnosti"], 45: ["fz53_kto_prizyvaetsya_vozrast_sroki", "fz53_otsrochka_ucheba"], 46: [S], 50: [],
     52: ["pp719_pereezd_i_vyezd", "fz53_uchet_gde_sostoyat_chto_soobshchat"], 64: ["pp663_raspredelenie_otpravka"], 77: ["neyavka_po_povestke"], 85: [], 86: [],
     87: [O], 97: ["pp565_analizy_pered_medkomissiey"], 107: ["povestka_vruchenie"], 113: [S]}
texts = json.load(open("отложенные_тексты.json", encoding="utf-8"))
with open("разметка_отложенные.jsonl", "w", encoding="utf-8") as f:
    for i, t in enumerate(texts):
        d, ok = ("здоровье", H[i]) if i in H else ("право", P[i]) if i in P else ("вне", [])
        f.write(json.dumps({"i": i, "вопрос": t, "источник": "mailru_calm_topic", "область": d, "ответы": ok}, ensure_ascii=False) + "\n")
import collections
print(collections.Counter(("здоровье" if i in H else "право" if i in P else "вне") for i in range(120)))
print("sha256", hashlib.sha256(open("разметка_отложенные.jsonl", "rb").read()).hexdigest())
