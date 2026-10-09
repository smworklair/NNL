# -*- coding: utf-8 -*-
"""Составной генератор задач v2 (ru, en). Задача = основа + цепочка действий; у каждого высказывания несколько
формулировок, ПОСЛЕДНЯЯ формулировка каждого банка — только для проверки («новые фразы»).
Решение — в формате GSM8K (<<выражение=результат>>результат … #### ответ). Все промежуточные числа — целые > 0.
Формулировки старого генератора для отложенных видов T8/T12/T14 сюда не входят (они остаются чужой проверкой)."""
import random

from генератор import NAMES_EN, NAMES_RU, NOUNS_EN, NOUNS_RU, RUB, plural

TRAIN, TEST = "train", "test"


def pick(bank, mode, rnd):
    """Из банка формулировок: для обучения — любая, кроме последней; для проверки — только последняя."""
    return bank[-1] if mode == TEST else rnd.choice(bank[:-1])


def calc(a, op, b):
    r = {"+": a + b, "-": a - b, "*": a * b, "/": a // b}[op]
    return r, "%d%s%d" % (a, op, b)


def step(expr_res):
    r, e = expr_res
    return r, "%s = <<%s=%d>>%d" % (e, e, r, r)


class RU:
    def __init__(self, rnd):
        self.rnd = rnd
        self.name, self.gen, self.g = rnd.choice(NAMES_RU)
        self.dat = self.name[:-1] + "е"
        self.noun = rnd.choice(NOUNS_RU)

    def v(self, m, f):
        return f if self.g == "f" else m

    @property
    def he(self):
        return self.v("он", "она")

    def n(self, k, forms=None):
        return "%d %s" % (k, plural(k, forms or self.noun))


class EN:
    def __init__(self, rnd):
        self.rnd = rnd
        self.name, self.g = rnd.choice(NAMES_EN)
        self.noun = rnd.choice(NOUNS_EN)
        self.gen = self.dat = self.name   # чтобы общие банки фраз вычислялись и для английского

    def v(self, m, f):
        return f if self.g == "f" else m

    @property
    def he(self):
        return self.v("he", "she")

    def n(self, k):
        return "%d %s" % (k, self.noun[0] if k == 1 else self.noun[1])


def num(rnd, lo, hi):
    while True:
        x = rnd.randint(lo, hi)
        if not (x % 10 == 1 and x % 100 != 11):
            return x


# ---------------- основа «цепочка действий над одним запасом» ----------------
def chain(lang, mode, rnd):
    s = RU(rnd) if lang == "ru" else EN(rnd)
    x = num(rnd, 20, 120)
    if lang == "ru":
        start = pick([lambda: "У %s было %s." % (s.gen, s.n(x)), lambda: "%s %s %s." % (s.name, s.v("собрал", "собрала"), s.n(x)),
                      lambda: "В коробке у %s лежало %s." % (s.gen, s.n(x)), lambda: "%s хранил%s %s." % (s.name, s.v("", "а"), s.n(x))], mode, rnd)()
    else:
        start = pick([lambda: "%s had %s." % (s.name, s.n(x)), lambda: "%s collected %s." % (s.name, s.n(x)),
                      lambda: "%s's box contained %s." % (s.name, s.n(x)), lambda: "%s kept %s." % (s.name, s.n(x))], mode, rnd)()
    sents, sol = [start], []
    for _ in range(rnd.randint(1, 3)):
        op = rnd.choice(("add", "mul") if x < 4 else ("add", "sub", "mul", "half") if x <= 400 else ("add", "sub", "half"))
        if op == "add":
            k = num(rnd, 2, 40)
            sents.append(pick({"ru": ["Потом %s %s ещё %d." % (s.he, s.v("купил", "купила"), k), "%s подарили ещё %d." % (s.dat, k),
                                      "%s %s ещё %d." % (s.he.capitalize(), s.v("нашёл", "нашла"), k), "Затем к ним добавилось ещё %d." % k,
                                      "Через день %s %s ещё %d." % (s.he, s.v("получил", "получила"), k)],
                               "en": ["Then %s bought %d more." % (s.he, k), "%s was given %d more." % (s.he.capitalize(), k),
                                      "%s found %d more." % (s.he.capitalize(), k), "Then %d more were added." % k,
                                      "A day later %s received %d more." % (s.he, k)]}[lang], mode, rnd))
            x, line = step(calc(x, "+", k))
            sol.append(("Стало " if lang == "ru" else "Now there are ") + line + ".")
        elif op == "sub":
            k = num(rnd, 2, max(2, min(40, x - 1)))
            sents.append(pick({"ru": ["Потом %s %s %d." % (s.he, s.v("отдал", "отдала"), k), "%s %s %d." % (s.he.capitalize(), s.v("потерял", "потеряла"), k),
                                      "%s %s %d." % (s.he.capitalize(), s.v("продал", "продала"), k), "Из них %d пришлось выбросить." % k,
                                      "Вечером %s %s %d соседу." % (s.he, s.v("подарил", "подарила"), k)],
                               "en": ["Then %s gave away %d." % (s.he, k), "%s lost %d." % (s.he.capitalize(), k),
                                      "%s sold %d." % (s.he.capitalize(), k), "%d of them had to be thrown away." % k,
                                      "In the evening %s gave %d to a neighbor." % (s.he, k)]}[lang], mode, rnd))
            x, line = step(calc(x, "-", k))
            sol.append(("Осталось " if lang == "ru" else "Left: ") + line + ".")
        elif op == "mul":
            k = rnd.randint(2, 4)
            sents.append(pick({"ru": ["Потом их стало в %d %s больше." % (k, plural(k, ("раз", "раза", "раз"))),
                                      "Затем %s %s запас в %d %s." % (s.he, s.v("увеличил", "увеличила"), k, plural(k, ("раз", "раза", "раз"))),
                                      "За месяц количество выросло в %d %s." % (k, plural(k, ("раз", "раза", "раз"))),
                                      "Потом %s %s их число в %d %s." % (s.he, s.v("умножил", "умножила"), k, plural(k, ("раз", "раза", "раз")))],
                               "en": ["Then there were %d times as many." % k, "Then %s multiplied the stock by %d." % (s.he, k),
                                      "In a month the amount grew %d times." % k, "Then %s made their number %d times larger." % (s.he, k)]}[lang], mode, rnd))
            x, line = step(calc(x, "*", k))
            sol.append(("Стало " if lang == "ru" else "Now there are ") + line + ".")
        else:
            if x % 2:
                k = 1
                x0 = x
                sents.append(pick({"ru": ["Потом %s %s 1." % (s.he, s.v("отдал", "отдала")), "%s %s 1." % (s.he.capitalize(), s.v("потерял", "потеряла")),
                                          "%s %s 1." % (s.he.capitalize(), s.v("продал", "продала")), "Из них 1 пришлось выбросить.", "Вечером %s %s 1 соседу." % (s.he, s.v("подарил", "подарила"))],
                                   "en": ["Then %s gave away 1." % s.he, "%s lost 1." % s.he.capitalize(), "%s sold 1." % s.he.capitalize(),
                                          "1 of them had to be thrown away.", "In the evening %s gave 1 to a neighbor." % s.he]}[lang], mode, rnd))
                x, line = step(calc(x0, "-", 1))
                sol.append(("Осталось " if lang == "ru" else "Left: ") + line + ".")
            sents.append(pick({"ru": ["Половину %s %s брату." % (s.he, s.v("отдал", "отдала")), "Потом %s %s половину." % (s.he, s.v("продал", "продала")),
                                      "Половина из них испортилась.", "Затем %s %s ровно половину друзьям." % (s.he, s.v("раздал", "раздала"))],
                               "en": ["%s gave half to %s brother." % (s.he.capitalize(), s.v("his", "her")), "Then %s sold half of them." % s.he,
                                      "Half of them went bad.", "Then %s gave exactly half to friends." % s.he]}[lang], mode, rnd))
            h, line1 = step(calc(x, "/", 2))
            x, line2 = step(calc(x, "-", h))
            sol.append(("Половина " if lang == "ru" else "Half is ") + line1 + "; " + ("осталось " if lang == "ru" else "left ") + line2 + ".")
    if lang == "ru":
        q = pick(["Сколько %s стало у %s?" % (s.noun[2], s.gen), "Сколько %s у %s теперь?" % (s.noun[2], s.v("него", "неё")),
                  "Сколько %s в итоге у %s?" % (s.noun[2], s.gen), "Сколько %s теперь у %s в запасе?" % (s.noun[2], s.gen)], mode, rnd)
    else:
        q = pick(["How many %s does %s have now?" % (s.noun[1], s.name), "How many %s are there now?" % s.noun[1],
                  "How many %s does %s end up with?" % (s.noun[1], s.he), "How many %s does %s have left in stock?" % (s.noun[1], s.name)], mode, rnd)
    return " ".join(sents + [q]), sol, x


# ---------------- основа «покупка» ----------------
def purchase(lang, mode, rnd):
    s = RU(rnd) if lang == "ru" else EN(rnd)
    qn, p = num(rnd, 2, 12), num(rnd, 3, 60)
    cost, l1 = step(calc(qn, "*", p))
    two = rnd.random() < 0.4
    money = rnd.random() < 0.5
    if lang == "ru":
        buy = pick(["%s %s %s по %s." % (s.name, s.v("купил", "купила"), s.n(qn), s.n(p, RUB)),
                    "%s %s %s, каждая штука стоила %s." % (s.name, s.v("взял", "взяла"), s.n(qn), s.n(p, RUB)),
                    "В магазине %s %s %s, цена одной штуки — %s." % (s.name, s.v("выбрал", "выбрала"), s.n(qn), s.n(p, RUB)),
                    "%s %s %s, заплатив за каждую %s." % (s.name, s.v("приобрёл", "приобрела"), s.n(qn), s.n(p, RUB))], mode, rnd)
        cur = "рублей"
    else:
        buy = pick(["%s bought %s for $%d each." % (s.name, s.n(qn), p), "%s took %s, each costing $%d." % (s.name, s.n(qn), p),
                    "At the store %s picked %s at $%d apiece." % (s.name, s.n(qn), p), "%s purchased %s, paying $%d for each." % (s.name, s.n(qn), p)], mode, rnd)
        cur = "dollars"
    sents, sol, total = [buy], [("Первая покупка: " if lang == "ru" else "First purchase: ") + l1 + " " + cur + "."], cost
    if two:
        q2, p2 = num(rnd, 2, 9), num(rnd, 3, 50)
        n2 = rnd.choice([x for x in (NOUNS_RU if lang == "ru" else NOUNS_EN) if x != s.noun])
        if lang == "ru":
            sents.append(pick(["Ещё %s %s %d %s по %s." % (s.he, s.v("взял", "взяла"), q2, plural(q2, n2), s.n(p2, RUB)),
                               "Кроме того, %s %s %d %s по %s." % (s.he, s.v("купил", "купила"), q2, plural(q2, n2), s.n(p2, RUB)),
                               "Потом %s %s ещё %d %s по %s." % (s.he, s.v("докупил", "докупила"), q2, plural(q2, n2), s.n(p2, RUB))], mode, rnd))
        else:
            sents.append(pick(["%s also took %d %s at $%d each." % (s.he.capitalize(), q2, n2[1], p2), "Besides, %s bought %d %s for $%d each." % (s.he, q2, n2[1], p2),
                               "Then %s added %d %s at $%d each." % (s.he, q2, n2[1], p2)], mode, rnd))
        c2, l2 = step(calc(q2, "*", p2))
        total, l3 = step(calc(cost, "+", c2))
        sol += [("Вторая покупка: " if lang == "ru" else "Second purchase: ") + l2 + " " + cur + ".", ("Всего " if lang == "ru" else "Total: ") + l3 + " " + cur + "."]
    if money:
        m = num(rnd, total + 5, total + 300)
        sents.insert(0, pick(["У %s было %s." % (s.gen, s.n(m, RUB)), "%s %s в магазин %s." % (s.name, s.v("взял", "взяла"), s.n(m, RUB)),
                              "В кошельке у %s лежало %s." % (s.gen, s.n(m, RUB))] if lang == "ru" else
                             ["%s had $%d." % (s.name, m), "%s took $%d to the store." % (s.name, m), "%s's wallet held $%d." % (s.name, m)], mode, rnd))
        left, l4 = step(calc(m, "-", total))
        sol.append(("Осталось " if lang == "ru" else "Left: ") + l4 + " " + cur + ".")
        q = pick(["Сколько рублей у %s осталось?" % s.v("него", "неё"), "Сколько рублей осталось у %s?" % s.gen, "Какая сдача у %s осталась в рублях?" % s.gen]
                 if lang == "ru" else ["How many dollars does %s have left?" % s.he, "How much money in dollars is left?", "How many dollars of change does %s keep?" % s.name], mode, rnd)
        return " ".join(sents + [q]), sol, left
    q = pick(["Сколько рублей %s %s?" % (s.he, s.v("потратил", "потратила")), "Сколько рублей стоила покупка?", "Сколько всего рублей %s %s?" % (s.he, s.v("заплатил", "заплатила"))]
             if lang == "ru" else ["How many dollars did %s spend?" % s.he, "How many dollars did the purchase cost?", "How many dollars did %s pay in total?" % s.he], mode, rnd)
    return " ".join(sents + [q]), sol, total


# ---------------- основа «сравнение» ----------------
def compare(lang, mode, rnd):
    s = RU(rnd) if lang == "ru" else EN(rnd)
    other = RU(rnd) if lang == "ru" else EN(rnd)
    while other.name == s.name:
        other = RU(rnd) if lang == "ru" else EN(rnd)
    a = num(rnd, 8, 80)
    rel = rnd.choice(("more", "less", "times"))
    k = num(rnd, 2, 30) if rel != "times" else rnd.randint(2, 5)
    if rel == "less":
        k = num(rnd, 2, a - 1)
    if lang == "ru":
        R = ("раз", "раза", "раз")
        base = pick(["У %s %s." % (s.gen, s.n(a)), "%s %s %s." % (s.name, s.v("насчитал", "насчитала"), s.n(a)), "У %s есть %s." % (s.gen, s.n(a))], mode, rnd)
        relt = {"more": pick(["У %s на %d больше." % (other.gen, k), "У %s их на %d больше." % (other.gen, k), "%s %s на %d больше." % (other.name, other.v("собрал", "собрала"), k)], mode, rnd),
                "less": pick(["У %s на %d меньше." % (other.gen, k), "У %s их на %d меньше." % (other.gen, k), "%s %s на %d меньше." % (other.name, other.v("собрал", "собрала"), k)], mode, rnd),
                "times": pick(["У %s в %d %s больше." % (other.gen, k, plural(k, R)), "У %s их в %d %s больше." % (other.gen, k, plural(k, R)),
                               "%s %s в %d %s больше." % (other.name, other.v("собрал", "собрала"), k, plural(k, R))], mode, rnd)}[rel]
    else:
        base = pick(["%s has %s." % (s.name, s.n(a)), "%s counted %s." % (s.name, s.n(a)), "%s owns %s." % (s.name, s.n(a))], mode, rnd)
        relt = {"more": pick(["%s has %d more." % (other.name, k), "%s has %d more of them." % (other.name, k), "%s collected %d more." % (other.name, k)], mode, rnd),
                "less": pick(["%s has %d fewer." % (other.name, k), "%s has %d fewer of them." % (other.name, k), "%s collected %d fewer." % (other.name, k)], mode, rnd),
                "times": pick(["%s has %d times as many." % (other.name, k), "%s has %d times as many of them." % (other.name, k), "%s collected %d times as many." % (other.name, k)], mode, rnd)}[rel]
    b, l1 = step(calc(a, {"more": "+", "less": "-", "times": "*"}[rel], k))
    sol = [("У %s " % other.gen if lang == "ru" else "%s has " % other.name) + l1 + "."]
    if rnd.random() < 0.5:
        tot, l2 = step(calc(a, "+", b))
        sol.append(("Вместе " if lang == "ru" else "Together: ") + l2 + ".")
        q = pick(["Сколько %s у них вместе?" % s.noun[2], "Сколько %s у обоих вместе?" % s.noun[2], "Сколько всего %s у %s и %s?" % (s.noun[2], s.gen, other.gen)]
                 if lang == "ru" else ["How many %s do they have together?" % s.noun[1], "How many %s do both have in total?" % s.noun[1],
                                       "How many %s do %s and %s have altogether?" % (s.noun[1], s.name, other.name)], mode, rnd)
        return " ".join([base, relt, q]), sol, tot
    q = pick(["Сколько %s у %s?" % (s.noun[2], other.gen), "Сколько %s у %s?" % (s.noun[2], other.gen), "Сколько %s насчитали у %s?" % (s.noun[2], other.gen)]
             if lang == "ru" else ["How many %s does %s have?" % (s.noun[1], other.name), "How many does %s have?" % other.name, "How many %s are counted for %s?" % (s.noun[1], other.name)], mode, rnd)
    return " ".join([base, relt, q]), sol, b


# ---------------- основа «скорость/норма × время» ----------------
def rate(lang, mode, rnd):
    s = RU(rnd) if lang == "ru" else EN(rnd)
    per, t = num(rnd, 3, 60), rnd.randint(2, 9)
    weeks = rnd.random() < 0.3
    if lang == "ru":
        txt = pick(["%s каждый день %s %s." % (s.name, s.v("делает", "делает"), s.n(per)), "За день %s %s %s." % (s.name, s.v("собирает", "собирает"), s.n(per)),
                    "Ежедневно %s получает %s." % (s.name, s.n(per)), "Каждый день к %s приходит %s." % (s.dat, s.n(per))], mode, rnd)
        if weeks:
            q = pick(["Сколько %s будет за %d %s?" % (s.noun[2], t, plural(t, ("неделю", "недели", "недель"))), "Сколько %s наберётся за %d %s?" % (s.noun[2], t, plural(t, ("неделю", "недели", "недель"))),
                      "Сколько %s получится за %d %s?" % (s.noun[2], t, plural(t, ("неделю", "недели", "недель")))], mode, rnd)
        else:
            q = pick(["Сколько %s будет за %d %s?" % (s.noun[2], t, plural(t, ("день", "дня", "дней"))), "Сколько %s наберётся за %d %s?" % (s.noun[2], t, plural(t, ("день", "дня", "дней"))),
                      "Сколько %s получится за %d %s?" % (s.noun[2], t, plural(t, ("день", "дня", "дней")))], mode, rnd)
    else:
        txt = pick(["%s makes %s every day." % (s.name, s.n(per)), "Each day %s collects %s." % (s.name, s.n(per)),
                    "Daily %s gets %s." % (s.name, s.n(per)), "Every day %s arrive for %s." % (s.n(per), s.name)], mode, rnd)
        unit = "weeks" if weeks else "days"
        q = pick(["How many %s will there be in %d %s?" % (s.noun[1], t, unit), "How many %s pile up in %d %s?" % (s.noun[1], t, unit),
                  "How many %s does it make in %d %s?" % (s.noun[1], t, unit)], mode, rnd)
    sol = []
    days = t
    if weeks:
        days, l0 = step(calc(t, "*", 7))
        sol.append(("Дней " if lang == "ru" else "Days: ") + l0 + ".")
    r, l1 = step(calc(days, "*", per))
    sol.append(("Всего " if lang == "ru" else "Total: ") + l1 + ".")
    return txt + " " + q, sol, r


# ---------------- основа «поровну / по столько-то» ----------------
def share(lang, mode, rnd):
    s = RU(rnd) if lang == "ru" else EN(rnd)
    k, each = rnd.randint(2, 9), num(rnd, 2, 25)
    a = k * each
    ask_groups = rnd.random() < 0.5
    if lang == "ru":
        if ask_groups:
            txt = pick(["%s %s %s в пакеты по %d." % (s.name, s.v("разложил", "разложила"), s.n(a), each), "%s нужно упаковать %s, в одну коробку помещается %d." % (s.dat, s.n(a), each),
                        "%s %s %s по %d в каждый мешочек." % (s.name, s.v("рассыпал", "рассыпала"), s.n(a), each)], mode, rnd)
            q = pick(["Сколько пакетов получилось?", "Сколько коробок понадобится?", "Сколько мешочков заполнилось?"], mode, rnd)
            r, l1 = step(calc(a, "/", each))
        else:
            txt = pick(["%s %s %s поровну между %d друзьями." % (s.name, s.v("разделил", "разделила"), s.n(a), k), "%s %s %s поровну на %d %s." % (s.name, s.v("раздал", "раздала"), s.n(a), k, plural(k, ("кучку", "кучки", "кучек"))),
                        "%s %s %s в %d одинаковых %s." % (s.name, s.v("разложил", "разложила"), s.n(a), k, plural(k, ("ящик", "ящика", "ящиков")))], mode, rnd)
            q = pick(["Сколько %s досталось каждому?" % s.noun[2], "Сколько %s в каждой части?" % s.noun[2], "Сколько %s в одной части?" % s.noun[2]], mode, rnd)
            r, l1 = step(calc(a, "/", k))
    else:
        if ask_groups:
            txt = pick(["%s packed %s into bags of %d." % (s.name, s.n(a), each), "%s needs to pack %s, %d fit in one box." % (s.name, s.n(a), each),
                        "%s poured %s into pouches, %d in each." % (s.name, s.n(a), each)], mode, rnd)
            q = pick(["How many bags were filled?", "How many boxes are needed?", "How many pouches were filled?"], mode, rnd)
            r, l1 = step(calc(a, "/", each))
        else:
            txt = pick(["%s shared %s equally among %d friends." % (s.name, s.n(a), k), "%s split %s equally into %d piles." % (s.name, s.n(a), k),
                        "%s put %s into %d identical crates." % (s.name, s.n(a), k)], mode, rnd)
            q = pick(["How many %s did each get?" % s.noun[1], "How many %s are in each part?" % s.noun[1], "How many %s are in one part?" % s.noun[1]], mode, rnd)
            r, l1 = step(calc(a, "/", k))
    return txt + " " + q, [("Получается " if lang == "ru" else "That is ") + l1 + "."], r


# ---------------- основа «за два дня» ----------------
def two_days(lang, mode, rnd):
    s = RU(rnd) if lang == "ru" else EN(rnd)
    a = num(rnd, 5, 60)
    rel = rnd.choice(("more", "less", "times"))
    k = rnd.randint(2, 4) if rel == "times" else num(rnd, 2, 20 if rel == "more" else max(2, a - 1))
    if lang == "ru":
        R = ("раз", "раза", "раз")
        d1 = pick(["В понедельник %s %s %s." % (s.name, s.v("сделал", "сделала"), s.n(a)), "Утром %s %s %s." % (s.name, s.v("собрал", "собрала"), s.n(a)),
                   "Сначала %s %s %s." % (s.name, s.v("получил", "получила"), s.n(a))], mode, rnd)
        d2 = {"more": pick(["Во вторник — на %d больше." % k, "Вечером — на %d больше." % k, "Потом — на %d больше, чем сначала." % k], mode, rnd),
              "less": pick(["Во вторник — на %d меньше." % k, "Вечером — на %d меньше." % k, "Потом — на %d меньше, чем сначала." % k], mode, rnd),
              "times": pick(["Во вторник — в %d %s больше." % (k, plural(k, R)), "Вечером — в %d %s больше." % (k, plural(k, R)), "Потом — в %d %s больше, чем сначала." % (k, plural(k, R))], mode, rnd)}[rel]
        q = pick(["Сколько %s всего?" % s.noun[2], "Сколько %s получилось за оба раза?" % s.noun[2], "Сколько %s вышло в сумме?" % s.noun[2]], mode, rnd)
    else:
        d1 = pick(["On Monday %s made %s." % (s.name, s.n(a)), "In the morning %s collected %s." % (s.name, s.n(a)), "At first %s got %s." % (s.name, s.n(a))], mode, rnd)
        d2 = {"more": pick(["On Tuesday, %d more." % k, "In the evening, %d more." % k, "Later, %d more than at first." % k], mode, rnd),
              "less": pick(["On Tuesday, %d fewer." % k, "In the evening, %d fewer." % k, "Later, %d fewer than at first." % k], mode, rnd),
              "times": pick(["On Tuesday, %d times as many." % k, "In the evening, %d times as many." % k, "Later, %d times as many as at first." % k], mode, rnd)}[rel]
        q = pick(["How many %s in total?" % s.noun[1], "How many %s were there over both times?" % s.noun[1], "How many %s in sum?" % s.noun[1]], mode, rnd)
    b, l1 = step(calc(a, {"more": "+", "less": "-", "times": "*"}[rel], k))
    tot, l2 = step(calc(a, "+", b))
    return " ".join([d1, d2, q]), [("Во второй раз " if lang == "ru" else "Second time: ") + l1 + ".", ("Всего " if lang == "ru" else "Total: ") + l2 + "."], tot


BASES = {"цепочка": chain, "покупка": purchase, "сравнение": compare, "норма": rate, "поровну": share, "два_раза": two_days}


def make(lang, mode, rnd):
    kind = rnd.choice(list(BASES))
    q, sol, ans = BASES[kind](lang, mode, rnd)
    return {"question": q, "answer": "\n".join(sol) + "\n#### %d" % ans, "вид": kind, "язык": lang, "фразы": mode}
