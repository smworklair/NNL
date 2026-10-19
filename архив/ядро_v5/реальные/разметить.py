# -*- coding: utf-8 -*-
"""Разметка 154 настоящих фраз (Documents/mailru_style/clean_seeds.jsonl: 138 с Ответов Mail.ru + 16 от учителя).
Разметил учитель (Claude) ДО запуска моделей. Метка: область (здоровье | право | вне) + допустимые ответы
(статьи / правовые темы; пусто — засчитывается только область). «вне» — правильный ответ системы «не знаю»."""
import hashlib, json, sys
sys.stdout.reconfigure(encoding="utf-8")
SRC = r"C:\Users\Admin\Documents\mailru_style\clean_seeds.jsonl"
U = "fz53_otsrochka_ucheba"; N = "neyavka_po_povestke"; S = "fz53_otsrochka_semeynye_obstoyatelstva"; O = "fz53_osvobozhdenie_ot_prizyva"
L = {
 0: ("здоровье", ["20"]), 1: ("вне", []), 2: ("право", [U]), 3: ("право", [U]), 4: ("вне", []), 5: ("вне", []), 6: ("вне", []), 7: ("вне", []),
 8: ("право", ["pp719_kto_obyazan_sostoyat_na_uchete", "fz53_kto_prizyvaetsya_vozrast_sroki"]), 9: ("право", ["kategorii_godnosti", "pp663_raspredelenie_otpravka"]),
 10: ("вне", []), 11: ("право", ["pp663_otsrochka_podtverzhdenie", "kak_prohodit_medkomissiya"]), 12: ("вне", []), 13: ("здоровье", ["7", "62"]),
 14: ("здоровье", ["66"]), 15: ("право", [N, "koap_uklonenie_ot_medobsledovaniya"]), 16: ("вне", []), 17: ("вне", []),
 18: ("право", ["fz53_prizyvnaya_komissiya_resheniya"]), 19: ("право", ["fz53_periody_otpravki", "fz53_kto_prizyvaetsya_vozrast_sroki"]), 20: ("вне", []),
 21: ("право", [U]), 22: ("право", [U]), 23: ("право", [U]), 24: ("право", [U]), 25: ("право", [U, "fz53_otsrochka_ukaz_it_sluzhba_prochie"]),
 26: ("право", ["pp719_kto_obyazan_sostoyat_na_uchete"]), 27: ("вне", []), 28: ("право", [O]), 29: ("вне", []), 30: ("вне", []), 31: ("вне", []),
 32: ("право", []), 33: ("право", ["fz53_proverit_elektronnuyu_povestku"]), 34: ("право", ["pp663_otsrochka_podtverzhdenie"]), 35: ("здоровье", ["71"]),
 36: ("право", [O]), 37: ("здоровье", ["62"]), 38: ("здоровье", ["54", "55", "56"]), 39: ("вне", []), 40: ("право", [O]), 41: ("право", ["kategorii_godnosti"]),
 42: ("право", [S]), 43: ("вне", []), 44: ("право", ["pp663_otsrochka_podtverzhdenie"]), 45: ("право", []), 46: ("вне", []),
 47: ("право", ["fz53_kto_prizyvaetsya_vozrast_sroki"]), 48: ("здоровье", ["68", "64"]), 49: ("здоровье", []), 50: ("вне", []), 51: ("здоровье", ["52"]),
 52: ("здоровье", ["52"]), 53: ("здоровье", []), 54: ("здоровье", []), 55: ("вне", []), 56: ("вне", []), 57: ("право", []), 58: ("право", []),
 59: ("право", ["napravlenie_na_obsledovanie"]), 60: ("право", ["kategorii_godnosti"]), 61: ("право", ["povestka_vruchenie", "fz53_obyazannost_yavki"]),
 62: ("право", ["obzhalovanie_resheniya_komissii", "nesoglasie_s_kategoriey", "kas_soderzhanie_administrativnogo_iska"]), 63: ("право", [N]), 64: ("право", [S]),
 65: ("право", []), 66: ("здоровье", []), 67: ("здоровье", ["58"]), 68: ("право", ["pripiska_17_let", "pp565_analizy_pered_medkomissiey"]), 69: ("здоровье", ["21"]),
 70: ("здоровье", ["40"]), 71: ("право", ["napravlenie_na_obsledovanie"]), 72: ("вне", []), 73: ("здоровье", []), 74: ("право", ["pp565_medosmotr_pered_otpravkoy"]),
 75: ("право", [U]), 76: ("право", [U]), 77: ("вне", []), 78: ("здоровье", ["66"]), 79: ("право", [U]), 80: ("право", [U]), 81: ("право", [S]), 82: ("право", [N]),
 83: ("право", [N, "fz53_rabota_ucheba_na_vremya_yavki"]), 84: ("право", []), 85: ("право", []), 86: ("вне", []), 87: ("вне", []), 88: ("здоровье", ["33"]),
 89: ("вне", []), 90: ("здоровье", ["17"]), 91: ("вне", []), 92: ("вне", []), 93: ("здоровье", []), 94: ("право", [U]), 95: ("здоровье", ["68"]),
 96: ("право", ["kategorii_godnosti"]), 97: ("здоровье", ["52"]), 98: ("здоровье", ["47"]), 99: ("право", [N, "ukrf_uklonenie_ot_prizyva"]), 100: ("право", []),
 101: ("право", [U, "fz53_reshenie_o_prizyve_srok_otmena"]), 102: ("право", ["utrata_dokumentov"]), 103: ("здоровье", []), 104: ("здоровье", ["45", "49"]),
 105: ("право", [N, "fz53_obyazannost_yavki"]), 106: ("вне", []), 107: ("здоровье", ["71", "72"]), 108: ("здоровье", []),
 109: ("право", ["pp719_kto_obyazan_sostoyat_na_uchete"]), 110: ("здоровье", ["66"]), 111: ("вне", []), 112: ("здоровье", ["51"]), 113: ("здоровье", ["62", "7"]),
 114: ("право", []), 115: ("право", ["fz53_uchet_gde_sostoyat_chto_soobshchat", "pp719_pereezd_i_vyezd"]), 116: ("вне", []), 117: ("право", []), 118: ("вне", []),
 119: ("здоровье", ["68"]), 120: ("право", [O, S]), 121: ("вне", []), 122: ("право", [U]), 123: ("вне", []), 124: ("вне", []), 125: ("вне", []), 126: ("право", [N]),
 127: ("право", ["napravlenie_na_obsledovanie"]), 128: ("право", [N]), 129: ("право", []), 130: ("право", ["utrata_dokumentov"]), 131: ("вне", []),
 132: ("право", ["nesoglasie_s_kategoriey", "obzhalovanie_resheniya_komissii"]), 133: ("вне", []), 134: ("право", []), 135: ("здоровье", ["43"]),
 136: ("право", []), 137: ("вне", []), 138: ("право", [N]), 139: ("право", ["nesoglasie_s_kategoriey"]), 140: ("право", []), 141: ("право", [U]),
 142: ("здоровье", ["65"]), 143: ("право", [N, "fz53_obyazannost_yavki", "povestka_vruchenie"]), 144: ("право", []), 145: ("здоровье", ["68", "66"]),
 146: ("право", [U, "pripiska_17_let"]), 147: ("право", ["napravlenie_na_obsledovanie"]), 148: ("право", [S]), 149: ("здоровье", ["71"]), 150: ("право", [N]),
 151: ("здоровье", ["34"]), 152: ("право", ["napravlenie_na_obsledovanie"]), 153: ("право", []),
}
rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
assert len(rows) == 154 and sorted(L) == list(range(154))
with open("разметка.jsonl", "w", encoding="utf-8") as f:
    for i, r in enumerate(rows):
        d, ok = L[i]
        f.write(json.dumps({"i": i, "вопрос": r["text"], "источник": r["source"], "область": d, "ответы": ok}, ensure_ascii=False) + "\n")
import collections
print(collections.Counter(v[0] for v in L.values()), "с конкретным ответом:", sum(1 for v in L.values() if v[1]))
print("sha256", hashlib.sha256(open("разметка.jsonl", "rb").read()).hexdigest())
