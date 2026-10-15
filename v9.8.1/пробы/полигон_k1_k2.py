# -*- coding: utf-8 -*-
"""Полигон K1 + K2: игрушечный мир с известной истиной и мостом.

Мир:
  - диагноз d из D болезней → категория годности c = f(d) ∈ {A,B,C,D}
  - обстоятельство o ∈ {o1,o2,o3,o4}
  - тема t = g(c, o) ∈ {t1..t8}

g выбрана так, что при ε=1 (полная нелинейность) аддитивная шина не справляется:
  g(c, o) = h((c_index + o_index) mod 4)  → латинский квадрат.

Блоки:
  - блок A читает текст, выдаёт p(c) — вероятность категории.
  - блок B читает текст + токен моста "м:категория:X", выдаёт p(t | c).

Сравниваем три сборки:
  1. solo_B: блок B не видит моста.
  2. шина: блок B видит аддитивную шину (взвешенное среднее категорий).
  3. k2: p(t) = Σ_c p_A(c)·p_B(t|c) — условный прогон.
"""
import json
import math
import os
import random
import sys

sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ВЫХОД = os.path.join(КОРЕНЬ, "v9", "результаты", "полигон_k1_k2.json")


# --------------------------------------------------------------------------- мир
КАТЕГОРИИ = ["A", "B", "C", "D"]
ОБСТОЯТЕЛЬСТВА = ["o1", "o2", "o3", "o4"]
ТЕМЫ = ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"]


def g(c, o):
    """Тема = XOR категории и обстоятельства (неаддитивный латинский квадрат).

    Для 4x4 это классическая таблица, которую нельзя представить в виде
    theme(c, o) = a_c + b_o; аддитивная шина v8 не справится, а K2 — да.
    """
    ci, oi = КАТЕГОРИИ.index(c), ОБСТОЯТЕЛЬСТВА.index(o)
    return ТЕМЫ[ci ^ oi]


# --------------------------------------------------------------------------- генерация вопросов
ГЕН = [
    "{diag} обнаружили у призывника, {obst}. Что делать?",
    "Призывник с {diag}, ситуация {obst}. Какая тема?",
    "Диагноз {diag}, обстоятельство {obst}. Итог?",
]


def текст(d, o):
    return random.choice(ГЕН).format(diag=d, obst=o)


def болезнь_по_категории(c):
    """Несколько болезней на категорию, чтобы текст зависел от категории."""
    base = КАТЕГОРИИ.index(c) * 4
    return [f"болезнь{base+i}" for i in range(4)]


# --------------------------------------------------------------------------- игрушечные блоки
class БлокА:
    """Предсказывает категорию по тексту. Немного ошибается."""
    def __init__(self, шум=0.1):
        self.шум = шум

    def категории(self, токены):
        """Возвращает {c: logit}."""
        # смотрим, какие болезни / категории в тексте
        scores = {c: 0.0 for c in КАТЕГОРИИ}
        for c in КАТЕГОРИИ:
            if any(t in токены for t in болезнь_по_категории(c)):
                scores[c] += 1.0
        # добавляем шум
        for c in scores:
            scores[c] += random.gauss(0, self.шум)
        return scores

    def вероятности(self, токены):
        scores = self.категории(токены)
        m = max(scores.values())
        e = {c: math.exp(v - m) for c, v in scores.items()}
        z = sum(e.values())
        return {c: e[c] / z for c in КАТЕГОРИИ}


class БлокБ:
    """Предсказывает тему по тексту и известной категории.
    Без категории — не выше случая.
    """
    def __init__(self, шум=0.1):
        self.шум = шум

    def темы(self, токены, мост_c=None):
        """Возвращает {t: logit}. Если мост_c известен, используем его."""
        # Из текста узнаём обстоятельство
        obst = None
        for o in ОБСТОЯТЕЛЬСТВА:
            if o in токены:
                obst = o
                break
        scores = {t: random.gauss(0, self.шум) for t in ТЕМЫ}
        if obst is not None and мост_c is not None:
            # знаем правильную тему
            правильная = g(мост_c, obst)
            for t in ТЕМЫ:
                if t == правильная:
                    scores[t] += 2.0
                elif t.startswith(правильная[:2]):  # похожая тема
                    scores[t] += 0.1
        elif obst is not None:
            # без категории — только группа тем подсказка по обстоятельству
            for c in КАТЕГОРИИ:
                t0 = g(c, obst)
                for t in ТЕМЫ:
                    if t == t0:
                        scores[t] += 0.3
                    elif t.startswith(t0[:2]):
                        scores[t] += 0.05
        return scores

    def вероятности(self, токены, мост_c=None):
        scores = self.темы(токены, мост_c)
        m = max(scores.values())
        e = {t: math.exp(v - m) for t, v in scores.items()}
        z = sum(e.values())
        return {t: e[t] / z for t in ТЕМЫ}


# --------------------------------------------------------------------------- сборки
def solo_B(текст, блокБ):
    """Блок Б без моста."""
    return блокБ.вероятности(текст)


def аддитивная_шина(текст, блокА, блокБ):
    """Шина = p_A взвешенная, подаётся в блок Б как мягкая смесь категорий."""
    p_A = блокА.вероятности(текст)
    # Аддитивная шина: усредняем счёты Б по категориям
    итог = {t: 0.0 for t in ТЕМЫ}
    for c, w in p_A.items():
        for t, p in блокБ.вероятности(текст, мост_c=c).items():
            итог[t] += w * p
    return итог


def k2(текст, блокА, блокБ):
    """Условный прогон: Σ_c p_A(c)·p_B(t|c)."""
    p_A = блокА.вероятности(текст)
    итог = {t: 0.0 for t in ТЕМЫ}
    for c, w in p_A.items():
        for t, p in блокБ.вероятности(текст, мост_c=c).items():
            итог[t] += w * p
    return итог


class ЖёсткаяБлокБ:
    """Блок Б с ограниченной score-level аддитивной шиной.

    Score для темы t = u_t(обстоятельство) + v_t(категория).
    Это имитация v8-шины: понятие категории приходит на шину как
    числовой вектор, а счёт ответа раскладывается в сумму
    «текстовая часть + шинная часть».
    Для XOR-таблицы такое представление невозможно, поэтому
    жёсткая шина должна проигрывать K2.
    """
    def __init__(self, lr=0.1, эпох=50):
        self.lr = lr
        self.эпох = эпох
        self.u = {}   # u[o][t]
        self.v = {}   # v[c][t]

    def обучить(self, данные):
        # Инициализация
        self.u = {o: {t: 0.0 for t in ТЕМЫ} for o in ОБСТОЯТЕЛЬСТВА}
        self.v = {c: {t: 0.0 for t in ТЕМЫ} for c in КАТЕГОРИИ}
        for _ in range(self.эпох):
            for r in данные:
                # softmax
                s = {t: self.u[r["o"]][t] + self.v[r["c"]][t] for t in ТЕМЫ}
                m = max(s.values())
                e = {t: math.exp(s[t] - m) for t in ТЕМЫ}
                z = sum(e.values())
                p = {t: e[t] / z for t in ТЕМЫ}
                # gradient update
                for t in ТЕМЫ:
                    target = 1.0 if t == r["t"] else 0.0
                    delta = (p[t] - target) * self.lr
                    self.u[r["o"]][t] -= delta
                    self.v[r["c"]][t] -= delta

    def вероятности(self, токены, мост_c=None):
        # Из текста узнаём обстоятельство
        obst = None
        for o in ОБСТОЯТЕЛЬСТВА:
            if o in токены:
                obst = o
                break
        if obst is None or мост_c is None:
            return {t: 1.0 / len(ТЕМЫ) for t in ТЕМЫ}
        s = {t: self.u[obst][t] + self.v[мост_c][t] for t in ТЕМЫ}
        m = max(s.values())
        e = {t: math.exp(s[t] - m) for t in ТЕМЫ}
        z = sum(e.values())
        return {t: e[t] / z for t in ТЕМЫ}


def жёсткая_аддитивная_шина(текст, блокА, жёсткаяБ):
    """v8-подобная шина: один жёсткий вектор категории, score = u + v."""
    c_top = топ1(блокА.вероятности(текст))
    return жёсткаяБ.вероятности(текст, мост_c=c_top)


# --------------------------------------------------------------------------- оценка
def топ1(p):
    return max(p, key=p.get)


def make_data(n=200, seed=0):
    rng = random.Random(seed)
    data = []
    for _ in range(n):
        c = rng.choice(КАТЕГОРИИ)
        o = rng.choice(ОБСТОЯТЕЛЬСТВА)
        d = rng.choice(болезнь_по_категории(c))
        t = g(c, o)
        data.append({
            "c": c, "o": o, "d": d, "t": t,
            "текст": текст(d, o),
        })
    return data


def evaluate(название, сборка, данные, блокА, блокБ):
    верно = 0
    for r in данные:
        p = сборка(r["текст"], блокА, блокБ) if "k2" in название or "шина" in название else сборка(r["текст"], блокБ)
        if топ1(p) == r["t"]:
            верно += 1
    return верно / len(данные)


def accuracy_для(сборка, данные, *args, **kwargs):
    верно = 0
    for r in данные:
        p = сборка(r["текст"], *args, **kwargs)
        if топ1(p) == r["t"]:
            верно += 1
    return верно / len(данные)


def main():
    random.seed(0)
    обучение = make_data(200, seed=0)
    тест = make_data(1000, seed=1)

    блокА = БлокА(шум=0.2)
    блокБ = БлокБ(шум=0.2)
    жёсткаяБ = ЖёсткаяБлокБ()
    жёсткаяБ.обучить(обучение)

    рез = {
        "полигон": "K1_K2_игрушка",
        "n_train": len(обучение),
        "n_test": len(тест),
        "категории": КАТЕГОРИИ,
        "обстоятельства": ОБСТОЯТЕЛЬСТВА,
        "темы": ТЕМЫ,
    }

    рез["accuracy"] = {
        "solo_B": accuracy_для(solo_B, тест, блокБ),
        "мягкая_аддитивная_шина": accuracy_для(аддитивная_шина, тест, блокА, блокБ),
        "жёсткая_аддитивная_шина": accuracy_для(жёсткая_аддитивная_шина, тест, блокА, жёсткаяБ),
        "k2": accuracy_для(k2, тест, блокА, блокБ),
    }

    рез["пример"] = {
        "текст": тест[0]["текст"],
        "истина": {"c": тест[0]["c"], "o": тест[0]["o"], "t": тест[0]["t"]},
        "p_A": {c: round(p, 3) for c, p in блокА.вероятности(тест[0]["текст"]).items()},
        "solo_B": {"top1": топ1(solo_B(тест[0]["текст"], блокБ)),
                   "p": {t: round(p, 3) for t, p in solo_B(тест[0]["текст"], блокБ).items()}},
        "k2": {"top1": топ1(k2(тест[0]["текст"], блокА, блокБ)),
               "p": {t: round(p, 3) for t, p in list(k2(тест[0]["текст"], блокА, блокБ).items())[:4]}},
    }

    os.makedirs(os.path.dirname(ВЫХОД), exist_ok=True)
    json.dump(рез, open(ВЫХОД, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(рез, ensure_ascii=False, indent=1))
    print("записано:", ВЫХОД)


if __name__ == "__main__":
    main()
