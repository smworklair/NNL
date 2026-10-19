# -*- coding: utf-8 -*-
"""Свежий проверочный набор v6: 200 случайных вопросов calm_topic (Ответы Mail.ru), которых не было ни в разметке v5,
ни в отложенных 120 (зерно 6006). Размечен учителем (Claude) ДО любых изменений v6; на нём v6 не настраивается.
Метка: «области» — допустимые области (первая — основная; «вне» = правильный ответ «не знаю»), «ответы» — допустимые
статьи / правовые темы (пусто — засчитывается только область). Остальные 1180 вопросов — пул для обучения (пул_тексты.json)."""
import hashlib, json, sys
sys.stdout.reconfigure(encoding="utf-8")
U = "fz53_otsrochka_ucheba"; N = "neyavka_po_povestke"; S = "fz53_otsrochka_semeynye_obstoyatelstva"; O = "fz53_osvobozhdenie_ot_prizyva"
V = "pp565_pereosvidetelstvovanie_kategoriya_v"; K = "kategorii_godnosti"; PV = "povestka_vruchenie"; UK = "ukrf_uklonenie_ot_prizyva"
H = {5: [], 20: ["34", "35"], 23: ["81", "67", "85"], 25: ["64", "65"], 52: ["57"], 65: ["2", "3"], 69: ["68"], 72: ["68"], 73: ["43"],
     77: ["27", "26"], 81: ["42"], 86: ["68", "65"], 87: ["42", "47"], 93: ["50", "10"], 98: [], 112: ["17"], 116: ["68", "86", "69"],
     147: ["34"], 153: [], 159: ["8", "10"], 161: ["14", "18"], 164: ["66", "81"], 169: ["68", "34", "43", "47"], 178: ["64", "65"],
     193: ["49"], 194: ["59", "86", "11"]}
P = {14: [], 16: ["koap_uklonenie_ot_medobsledovaniya", "napravlenie_na_obsledovanie"], 22: [],
     28: ["fz53_ne_sluzhil_do_30_zaklyuchenie", "fz53_obyazannost_yavki"], 33: ["fz53_prizyvnaya_komissiya_resheniya", UK], 34: [O],
     38: [V, PV], 43: ["napravlenie_na_obsledovanie"], 45: ["fz53_obyazannost_yavki"], 46: ["fz53_srok_sluzhby_uvolnenie"], 58: [V, K], 60: [V],
     62: ["pp719_pereezd_i_vyezd", "fz53_zapret_vyezda_povestka"], 64: [V], 68: [], 74: [O], 75: [], 79: [], 84: [U],
     89: ["kak_napisat_zhalobu", "fz59_srok_otveta_i_net_otveta", "obzhalovanie_resheniya_komissii"], 92: [S], 95: [U], 96: ["kak_napisat_zhalobu"],
     97: [V], 105: ["fz53_ne_sluzhil_do_30_zaklyuchenie"], 119: [PV], 126: [], 130: ["kak_prohodit_medkomissiya", K],
     131: ["pp663_otsrochka_podtverzhdenie"], 132: [UK], 136: [S], 139: [PV, N], 142: [N], 144: [U], 158: ["napravlenie_na_obsledovanie", K],
     163: [N, UK], 172: [N, UK], 175: ["pp663_raspredelenie_otpravka", K],
     185: ["fz53_uchet_gde_sostoyat_chto_soobshchat", "koap_nesoobshchenie_izmeneniy_pereezd", "pp719_pereezd_i_vyezd"], 187: [PV], 190: [U],
     196: ["pripiska_17_let", "utrata_dokumentov"]}
A = {30: (["право", "вне"], []), 35: (["вне", "право"], []), 53: (["право", "вне"], ["fz53_prizyvnaya_komissiya_resheniya"]),
     90: (["право", "вне"], ["pp565_analizy_pered_medkomissiey"]), 99: (["вне", "право"], []), 100: (["вне", "право"], []),
     118: (["вне", "право"], []), 124: (["вне", "право"], []), 127: (["право", "вне"], []), 135: (["право", "вне"], [U]),
     138: (["вне", "здоровье"], ["68"]), 150: (["вне", "право"], []), 173: (["вне", "право"], [])}
assert not (set(H) & set(P)) and not (set(A) & (set(H) | set(P)))
texts = json.load(open("свежие_тексты.json", encoding="utf-8"))
with open("разметка_свежие.jsonl", "w", encoding="utf-8") as f:
    for i, t in enumerate(texts):
        if i in H:
            ar, ok = ["здоровье"], H[i]
        elif i in P:
            ar, ok = ["право"], P[i]
        elif i in A:
            ar, ok = A[i]
        else:
            ar, ok = ["вне"], []
        f.write(json.dumps({"i": i, "вопрос": t, "источник": "mailru_calm_topic", "область": ar[0], "области": ar, "ответы": ok},
                           ensure_ascii=False) + "\n")
import collections
print(collections.Counter(("здоровье" if i in H else "право" if i in P else "спорно" if i in A else "вне") for i in range(len(texts))))
print("sha256", hashlib.sha256(open("разметка_свежие.jsonl", "rb").read()).hexdigest())
