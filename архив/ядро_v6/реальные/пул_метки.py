# -*- coding: utf-8 -*-
"""Метки учителя (Claude) для обучающего пула (пул_тексты.json, 1180 вопросов calm_topic).
P — право (темы; пусто — область права без точной темы), H — здоровье (статьи; пусто — без точной статьи),
SKIP — спорные, в обучение не идут. Остальное — «вне» (вопрос не о праве призыва и не о здоровье)."""
U = "fz53_otsrochka_ucheba"; N = "neyavka_po_povestke"; S = "fz53_otsrochka_semeynye_obstoyatelstva"; O = "fz53_osvobozhdenie_ot_prizyva"
V = "pp565_pereosvidetelstvovanie_kategoriya_v"; K = "kategorii_godnosti"; PV = "povestka_vruchenie"; UK = "ukrf_uklonenie_ot_prizyva"
UCH = "fz53_uchet_gde_sostoyat_chto_soobshchat"; PER = "pp719_pereezd_i_vyezd"; MK = "kak_prohodit_medkomissiya"; AN = "pp565_analizy_pered_medkomissiey"
OB = "napravlenie_na_obsledovanie"; UT = "utrata_dokumentov"; YA = "fz53_obyazannost_yavki"; PD = "pp663_otsrochka_podtverzhdenie"

P = {}
H = {}
SKIP = set()

# 0–299
P.update({2: [YA, UCH], 5: [PER, "fz53_zapret_vyezda_povestka"], 7: [], 17: [OB], 19: [], 28: [O], 35: [S], 40: [UCH, PER], 42: [V, K],
          47: [MK], 48: ["fz53_periody_otpravki"], 50: [MK, AN], 51: [], 54: [YA, UT], 55: [], 60: [PD, O],
          67: ["kas_rassmotrenie_dela_srok_dokazyvanie", "obzhalovanie_resheniya_komissii"], 72: [PD], 74: [OB], 77: [UT], 79: [AN], 82: [O],
          83: [UCH], 87: [MK], 94: [U, "koap_nesoobshchenie_izmeneniy_pereezd"], 108: [N], 111: [U], 121: [PV, PER], 123: [AN, OB], 124: [UT],
          134: [N, UK], 146: ["pp719_kto_obyazan_sostoyat_na_uchete"], 154: [U], 161: [S], 164: [UT], 178: [N],
          181: ["fz53_otsrochka_ukaz_it_sluzhba_prochie"], 182: ["kas_rassmotrenie_dela_srok_dokazyvanie"], 184: ["pripiska_17_let", O], 185: [O],
          186: [UCH], 193: [S], 194: [O, K], 196: [], 200: [], 203: ["nesoglasie_s_kategoriey", "pp565_medosmotr_pered_otpravkoy"], 212: [MK],
          213: [S], 219: [MK], 221: [UCH, PER], 226: [U], 240: [], 241: [U], 254: [MK, "fz53_kto_prizyvaetsya_vozrast_sroki"],
          257: ["fz53_kto_prizyvaetsya_vozrast_sroki"], 258: [U], 260: ["pripiska_17_let", "koap_nesoobshchenie_izmeneniy_pereezd"], 262: [AN],
          265: [U], 275: ["pp719_kto_obyazan_sostoyat_na_uchete"], 276: [U], 280: [UCH], 281: [U], 284: [], 287: [PER, UCH], 290: [MK], 291: [YA],
          293: ["fz53_rabota_ucheba_na_vremya_yavki"]})
H.update({1: ["17", "18"], 22: ["23"], 29: ["52"], 30: ["42", "47"], 36: ["19"], 45: ["66"], 52: ["70"], 56: ["12", "13"], 58: [], 65: ["23"],
          70: ["15"], 71: ["49"], 85: [], 122: ["58"], 128: ["65"], 130: ["47"], 145: ["68"], 159: ["14", "18"], 165: ["47"], 191: ["62"],
          207: ["68"], 222: ["56"], 225: ["21"], 238: ["71"], 243: ["68"], 244: ["65"], 248: ["34", "35"], 259: [], 264: ["42", "47"], 278: ["66"]})
SKIP |= {20, 38, 66, 75, 76, 91, 104, 105, 135, 155, 160, 166, 179, 188, 204, 205, 216, 220, 223, 263, 268}

# 300–599
P.update({300: ["pp719_kto_obyazan_sostoyat_na_uchete"], 304: [OB, K], 306: ["fz53_periody_otpravki"], 308: [U], 310: [], 311: [UT], 320: [],
          324: [U], 334: ["fz53_srok_sluzhby_uvolnenie"], 335: [UCH], 340: [], 346: [UT], 356: ["fz53_otsrochka_ukaz_it_sluzhba_prochie"],
          362: [PER, UCH], 368: [PD], 375: [S], 387: [U], 390: [K], 395: ["pp663_raspredelenie_otpravka"], 400: [], 404: [U], 407: [U], 408: [PD, O],
          414: [], 418: ["fz53_zapret_vyezda_povestka", PER], 420: [S], 423: [S],
          425: ["obzhalovanie_resheniya_komissii", "nesoglasie_s_kategoriey", "kas_soderzhanie_administrativnogo_iska"], 427: [AN, PD],
          432: ["pp719_kto_obyazan_sostoyat_na_uchete"], 441: ["fz53_otsrochka_ukaz_it_sluzhba_prochie"], 443: [U], 453: [UCH], 456: [PD], 459: [MK],
          460: [UK, "fz53_proverit_elektronnuyu_povestku"], 465: [S], 478: [UCH, "pp719_kto_obyazan_sostoyat_na_uchete"], 482: [MK], 485: [MK],
          486: ["fz53_srok_sluzhby_uvolnenie"], 487: [], 494: [], 495: ["kas_soderzhanie_administrativnogo_iska", "obzhalovanie_resheniya_komissii"],
          499: ["fz53_kto_prizyvaetsya_vozrast_sroki"], 503: [AN], 510: [U], 514: [YA], 523: [AN], 528: [S], 531: [U], 539: [MK],
          540: ["pp565_medosmotr_pered_otpravkoy"], 542: [U], 544: [V], 549: [PER, UCH], 553: [OB], 559: [U], 564: [O], 566: [O], 569: [O], 574: [OB],
          580: ["pripiska_17_let"], 581: ["pp663_raspredelenie_otpravka"], 592: [PER]})
H.update({303: [], 319: [], 329: ["65"], 331: [], 357: ["49"], 378: ["66", "68", "65"], 383: ["68"], 388: ["43"], 411: [], 422: [], 433: ["18"],
          436: ["35", "30"], 439: ["49"], 446: ["51", "52"], 447: ["21"], 452: ["65"], 475: ["21"], 480: ["86", "59"], 481: ["57"], 484: ["66"],
          493: ["24", "43"], 501: ["52"], 508: ["14", "18"], 520: ["42"], 527: ["71", "34"], 561: ["59"], 562: ["17", "18"], 568: ["17", "18"]})
SKIP |= {369, 377, 398, 428, 451, 466, 473, 483, 498, 516, 599}

# 600–899
P.update({606: [O], 613: [V], 617: ["pp663_raspredelenie_otpravka"], 621: [U], 622: [U], 624: ["fz53_periody_otpravki"], 628: [U],
          630: ["fz53_otsrochka_ukaz_it_sluzhba_prochie"], 635: [], 637: ["pp663_raspredelenie_otpravka", K], 640: [MK, PD], 650: [],
          651: [PER, "fz53_zapret_vyezda_povestka"], 658: [U], 659: [], 663: ["fz53_periody_otpravki"], 673: [U], 674: [K], 676: [], 677: [U], 679: [O],
          681: [], 687: [S], 688: [O], 693: [MK, "fz53_periody_otpravki"], 701: ["pp663_raspredelenie_otpravka"], 703: [U],
          707: ["pp663_raspredelenie_otpravka"], 714: [], 715: [MK], 721: [N, PV, UK], 727: [N], 730: [MK], 737: [U],
          741: [UCH, "koap_nesoobshchenie_izmeneniy_pereezd"], 755: [PER], 758: [PER], 772: [UCH], 782: [MK], 793: [S],
          798: ["fz53_zapret_vyezda_povestka", PER], 806: ["pp565_medosmotr_pered_otpravkoy"], 811: ["fz53_periody_otpravki"], 819: [U, "pripiska_17_let"],
          824: ["pp663_raspredelenie_otpravka"], 828: ["fz53_zapret_vyezda_povestka"], 831: ["pp719_kto_obyazan_sostoyat_na_uchete"],
          837: ["pp663_raspredelenie_otpravka", K], 840: [U], 852: [PV], 855: [O], 868: [S], 877: [PER, UCH], 885: [V], 891: [U],
          897: ["fz53_prizyvnaya_komissiya_resheniya", O]})
H.update({609: ["57", "59", "72"], 623: ["13", "12", "86"], 641: ["17"], 643: ["24"], 645: ["25", "28"], 646: [], 648: ["23"], 655: [], 668: ["17"],
          686: ["68"], 690: ["51", "2"], 691: ["46"], 696: ["17"], 719: ["43"], 726: ["58"], 731: ["68"], 735: ["55"], 743: ["59"], 744: ["17", "18"],
          748: ["47"], 751: ["52"], 754: [], 763: [], 765: ["47", "49", "68", "67"], 769: [], 770: ["59"], 783: ["11"], 794: ["17", "18"], 802: ["81"],
          814: ["43"], 816: ["42"], 821: ["51"], 838: ["34", "35"], 856: [], 865: ["64"], 866: ["17"], 876: ["72", "71"]})
SKIP |= {605, 626, 631, 662, 750, 757, 784, 785, 797, 800, 867, 872, 881, 889}

# 900–1179
P.update({901: [], 903: [UT], 908: ["pp663_raspredelenie_otpravka"], 929: ["pp663_raspredelenie_otpravka"], 932: [PER, "pp719_kto_obyazan_sostoyat_na_uchete"],
          939: [AN, MK], 942: [OB], 946: ["fz53_reshenie_o_prizyve_srok_otmena", "pp663_raspredelenie_otpravka"], 949: [], 961: [U], 971: [MK, PD],
          974: ["pp719_kto_obyazan_sostoyat_na_uchete"], 985: ["pp663_raspredelenie_otpravka"], 987: [PD, MK], 989: ["pp663_raspredelenie_otpravka", K],
          997: ["fz53_zapret_vyezda_povestka"], 1007: [PER], 1010: ["pp565_medosmotr_pered_otpravkoy"], 1012: [AN], 1015: [U], 1043: [U], 1048: [U],
          1055: [], 1066: [PER], 1076: [AN], 1084: [U], 1088: [AN, PD], 1092: [MK], 1099: ["pripiska_17_let"], 1103: [UCH, "pripiska_17_let"],
          1110: [PV, YA], 1119: [U], 1125: [S], 1140: [K], 1141: ["pp663_raspredelenie_otpravka"], 1158: [U], 1166: [YA, UT], 1168: [O, K],
          1170: [N, UK], 1173: [U], 1176: ["pp663_raspredelenie_otpravka"]})
H.update({904: ["17"], 907: ["71"], 911: ["47", "17"], 912: ["25", "80"], 924: ["34", "36"], 928: [], 935: ["19"], 936: [], 943: ["65", "81"],
          969: ["47", "17"], 970: [], 973: [], 1004: ["47"], 1011: ["42"], 1016: ["9"], 1017: [], 1030: ["68", "66", "42"], 1033: ["57"], 1050: ["21"],
          1053: ["42"], 1056: ["72", "78"], 1062: ["65"], 1086: ["47"], 1093: [], 1104: [], 1115: ["42"], 1122: ["58"], 1151: []})
SKIP |= {918, 919, 922, 937, 963, 968, 978, 1018, 1068, 1089, 1090, 1106, 1107, 1111}
