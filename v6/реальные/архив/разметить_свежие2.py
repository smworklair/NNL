# -*- coding: utf-8 -*-
"""Разметка свежие2 (200 из архива Ответов Mail.ru) учителем (Claude) ДО замера на них. Метки как в разметить_свежие.py."""
import hashlib, json, sys
sys.stdout.reconfigure(encoding="utf-8")
U = "fz53_otsrochka_ucheba"; N = "neyavka_po_povestke"; S = "fz53_otsrochka_semeynye_obstoyatelstva"; O = "fz53_osvobozhdenie_ot_prizyva"
V = "pp565_pereosvidetelstvovanie_kategoriya_v"; K = "kategorii_godnosti"; PV = "povestka_vruchenie"; UK = "ukrf_uklonenie_ot_prizyva"
UCH = "fz53_uchet_gde_sostoyat_chto_soobshchat"; PER = "pp719_pereezd_i_vyezd"; YA = "fz53_obyazannost_yavki"; OB = "napravlenie_na_obsledovanie"
UT = "utrata_dokumentov"; RO = "pp663_raspredelenie_otpravka"; P30 = "fz53_ne_sluzhil_do_30_zaklyuchenie"; PP = "pp719_kto_obyazan_sostoyat_na_uchete"
PR = "pripiska_17_let"; PD = "pp663_otsrochka_podtverzhdenie"; PE = "fz53_periody_otpravki"
H = {3: ["86"], 17: ["66", "81"], 19: ["57"], 24: ["66"], 60: ["81"], 66: ["43"], 76: ["52", "34"], 90: ["86"], 94: ["34"], 95: ["81", "65"],
     99: ["66"], 118: ["68"], 120: ["66"], 132: ["14"], 138: ["68"], 143: ["58"], 165: ["22", "25"], 178: ["56"], 181: ["40"], 186: ["72"]}
P = {0: [U], 4: [S], 9: [OB], 11: ["obzhalovanie_resheniya_komissii"], 14: [U], 15: [S], 16: ["koap_uklonenie_ot_medobsledovaniya"], 21: [U], 22: [U],
     27: [U, PE], 28: [S], 37: [], 44: [RO], 45: [PV, N], 48: [U], 49: [PP, O], 50: [U], 53: [RO], 54: [N], 63: [U], 65: [S], 70: [PE],
     72: [PR, PD], 74: [UK], 81: [PER], 84: ["fz53_srok_sluzhby_uvolnenie"], 92: [P30], 93: [PP, PR, UK], 104: [U], 105: [], 106: [], 108: [V, K],
     116: [N, UK], 124: [UT], 140: [UCH, PER], 144: [P30, UCH], 146: [PER, UCH], 147: [YA, PV], 149: [PR, UCH], 154: [PP], 158: [P30, PP], 159: [],
     160: [], 163: ["fz53_reshenie_o_prizyve_srok_otmena"], 167: [], 172: [UCH, PR, "koap_nesoobshchenie_izmeneniy_pereezd"], 173: [UK], 174: [N, YA],
     176: [P30, K], 179: ["fz53_srok_sluzhby_uvolnenie", PE], 184: [V], 189: [K], 190: [U], 193: [U], 195: [PER, UK], 197: []}
A = {1: (["вне", "здоровье"], []), 5: (["здоровье", "вне"], ["71", "72"]), 8: (["право", "вне"], []), 12: (["вне", "право"], []), 30: (["право", "вне"], [PER]),
     33: (["вне", "право"], []), 56: (["здоровье", "право", "вне"], []), 75: (["здоровье", "право"], ["34"]), 79: (["вне", "право", "здоровье"], []),
     82: (["право", "здоровье"], []), 112: (["здоровье", "вне"], ["21"]), 128: (["здоровье", "вне"], []), 131: (["вне", "право"], []), 164: (["вне", "здоровье"], [])}
assert not (set(H) & set(P)) and not (set(A) & (set(H) | set(P)))
texts = [r["текст"] for r in json.load(open("свежие2_тексты.json", encoding="utf-8"))]
with open("разметка_свежие2.jsonl", "w", encoding="utf-8") as f:
    for i, t in enumerate(texts):
        ar, ok = (["здоровье"], H[i]) if i in H else (["право"], P[i]) if i in P else A.get(i, (["вне"], []))
        f.write(json.dumps({"i": i, "вопрос": t, "источник": "архив_mailru", "область": ar[0], "области": ar, "ответы": ok}, ensure_ascii=False) + "\n")
import collections
print(collections.Counter(("здоровье" if i in H else "право" if i in P else "спорно" if i in A else "вне") for i in range(len(texts))))
print("sha256", hashlib.sha256(open("разметка_свежие2.jsonl", "rb").read()).hexdigest())
