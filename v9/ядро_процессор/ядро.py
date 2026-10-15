# -*- coding: utf-8 -*-
"""Ядро (Причинный валидатор).

Отвечает за проверку причинных ролей, проекцию фактов и консистентность:
  1. Паспортный причинный протокол: проекция ответа в понятия шины.
  2. Проверка причинных контрактов (preconditions, исключения, несовместимости).
  3. Устранение причинных рассогласований в цепочке рассуждения.
"""
import os


class Ядро:
    def __init__(self, база_путь):
        self.база_путь = база_путь
        self.статья_глава = {}
        self.тема_акты = {}
        self._загрузить_базу()

    def _загрузить_базу(self):
        # Загрузка отображений статья -> глава
        sg_path = os.path.join(self.база_путь, "математичка", "данные", "статья_глава.csv")
        if os.path.exists(sg_path):
            with open(sg_path, encoding="utf-8") as f:
                f.readline()
                for line in f:
                    if line.strip():
                        p = line.strip().split(";")
                        self.статья_глава[p[0]] = p[1]

        # Загрузка отображений тема -> акты
        ta_path = os.path.join(self.база_путь, "математичка", "данные", "тема_акты.csv")
        if os.path.exists(ta_path):
            with open(ta_path, encoding="utf-8") as f:
                f.readline()
                for line in f:
                    if line.strip():
                        p = line.strip().split(";")
                        topic = p[0]
                        acts = []
                        for a in p[1].split("+"):
                            a = a.strip()
                            if "53фз" in a: acts.append("акт:53фз")
                            elif "пп565" in a: acts.append("акт:пп565")
                            elif "пп663" in a: acts.append("акт:пп663")
                            elif "пп719" in a: acts.append("акт:пп719")
                            elif "кас" in a: acts.append("акт:кас")
                            elif "коап" in a: acts.append("акт:коап")
                            elif "укрф" in a: acts.append("акт:укрф")
                            elif "127фз" in a: acts.append("акт:127фз")
                            elif "59фз" in a: acts.append("акт:59фз")
                        self.тема_акты[topic] = acts

    def проецировать_на_шину(self, имя_блока, ответ):
        """Проецирует вывод блока в стандартизованные понятия шины согласно паспорту."""
        проекция = {}
        if имя_блока == "здоровье":
            art_id = ответ.replace("ответ:здоровье:", "")
            chap = self.статья_глава.get(art_id)
            проекция["область:здоровье"] = 16.0
            if chap:
                проекция[f"глава:{chap}"] = 16.0
        elif имя_блока == "право":
            top_id = ответ.replace("ответ:право:", "")
            acts = self.тема_акты.get(top_id, [])
            проекция["область:право"] = 16.0
            for a in acts:
                проекция[a] = 16.0
        return проекция

    def проверить_цепочку(self, отклики):
        """Проверяет причинную совместимость ответов и устраняет противоречия."""
        рез = {}
        for k, v in отклики.items():
            рез[k] = dict(v)

        # Контракт причинной совместимости:
        # Если подтверждён медицинский базис (блок здоровье уверен),
        # немедицинские процедурные темы (отсрочка по учебе/семье, не регулируемые ПП 565)
        # являются причинно несовместимыми с наличием клинического диагноза.
        non_med_deferments = {
            "ответ:право:fz53_otsrochka_ucheba",
            "ответ:право:fz53_otsrochka_semeynye_obstoyatelstva",
            "ответ:право:fz53_otsrochka_ukaz_it_sluzhba_prochie",
        }

        zd = рез.get("здоровье")
        pr = рез.get("право")
        if zd and pr and zd["margin"] >= 1.0:
            if pr["top1"] in non_med_deferments:
                # Фильтруем причинно несовместимые гипотезы в распределении права
                фильтр_счёты = {k: v for k, v in pr["счёты"].items() if k not in non_med_deferments}
                if фильтр_счёты:
                    сортировка = sorted(фильтр_счёты.items(), key=lambda x: x[1], reverse=True)
                    top1_ans, top1_score = сортировка[0]
                    top2_score = сортировка[1][1] if len(сортировка) > 1 else top1_score
                    рез["право"]["top1"] = top1_ans
                    рез["право"]["score"] = top1_score
                    рез["право"]["margin"] = top1_score - top2_score
                    рез["право"]["счёты"] = фильтр_счёты
                    рез["право"]["причинная_коррекция"] = "устранена несовместимая немедицинская отсрочка"

        return рез
