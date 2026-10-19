# -*- coding: utf-8 -*-
"""Генератор простых текстовых задач (1–3 действия) на русском и английском с решением по шагам в формате GSM8K:
каждое вычисление записано как <<выражение=результат>>, в конце «#### ответ». Все промежуточные числа — целые > 0.
Виды T8, T12, T14 в обучение не идут (проверка на незнакомых формулировках)."""
import random

HELD_OUT = ("T8", "T12", "T14")

# имя, родительный падеж, пол
NAMES_RU = [("Маша", "Маши", "f"), ("Петя", "Пети", "m"), ("Аня", "Ани", "f"), ("Дима", "Димы", "m"), ("Оля", "Оли", "f"),
            ("Коля", "Коли", "m"), ("Лена", "Лены", "f"), ("Миша", "Миши", "m"), ("Катя", "Кати", "f"), ("Ваня", "Вани", "m"),
            ("Ира", "Иры", "f"), ("Саша", "Саши", "m"), ("Таня", "Тани", "f"), ("Гоша", "Гоши", "m"), ("Вера", "Веры", "f")]
NAMES_EN = [("Mary", "f"), ("Peter", "m"), ("Anna", "f"), ("David", "m"), ("Olivia", "f"), ("Nick", "m"), ("Lena", "f"),
            ("Mike", "m"), ("Kate", "f"), ("John", "m"), ("Iris", "f"), ("Sam", "m"), ("Tina", "f"), ("George", "m"), ("Vera", "f")]
# существительное: (1, 2–4, 5+) — винительный для 2–4/5+ совпадает с этими формами у выбранных слов
NOUNS_RU = [("яблоко", "яблока", "яблок"), ("конфета", "конфеты", "конфет"), ("тетрадь", "тетради", "тетрадей"),
            ("карандаш", "карандаша", "карандашей"), ("марка", "марки", "марок"), ("книга", "книги", "книг"),
            ("шарик", "шарика", "шариков"), ("наклейка", "наклейки", "наклеек"), ("орех", "ореха", "орехов"),
            ("открытка", "открытки", "открыток"), ("ручка", "ручки", "ручек"), ("пирожок", "пирожка", "пирожков")]
NOUNS_EN = [("apple", "apples"), ("candy", "candies"), ("notebook", "notebooks"), ("pencil", "pencils"), ("stamp", "stamps"),
            ("book", "books"), ("balloon", "balloons"), ("sticker", "stickers"), ("nut", "nuts"), ("postcard", "postcards"),
            ("pen", "pens"), ("pie", "pies")]
RUB = ("рубль", "рубля", "рублей")


def plural(n, forms):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def num(rnd, lo, hi, ok_one=False):
    """Случайное целое; без окончания на 1 (кроме 11), чтобы не возиться с падежами при «21 конфету»."""
    while True:
        x = rnd.randint(lo, hi)
        if ok_one or not (x % 10 == 1 and x % 100 != 11):
            return x


def v(g, m, f):
    return f if g == "f" else m


def calc(a, op, b):
    r = {"+": a + b, "-": a - b, "*": a * b, "/": a // b}[op]
    return r, "%d%s%d=%d" % (a, op, b, r)


def gen_ru(kind, rnd):
    name, gen, g = rnd.choice(NAMES_RU)
    nf = rnd.choice(NOUNS_RU)
    he, him = v(g, "он", "она"), v(g, "него", "неё")
    if kind == "T1":
        a, b, c = num(rnd, 12, 90), num(rnd, 2, 11), num(rnd, 2, 30)
        r1, e1 = calc(a, "-", b)
        r2, e2 = calc(r1, "+", c)
        q = "У %s было %d %s. %s %s %d, а потом %s ещё %d. Сколько %s стало у %s?" % (
            gen, a, plural(a, nf), he.capitalize(), v(g, "отдал", "отдала"), b, v(g, "купил", "купила"), c, nf[2], gen)
        s = ["После того как %s %s %d, осталось %s = <<%s>>%d." % (he, v(g, "отдал", "отдала"), b, e1.split("=")[0], e1, r1),
             "Потом стало %s = <<%s>>%d." % (e2.split("=")[0], e2, r2)]
        return q, s, r2
    if kind == "T2":
        qn, p = num(rnd, 2, 19), num(rnd, 3, 95)
        r, e = calc(qn, "*", p)
        q = "%s %s %d %s по %d %s. Сколько рублей %s %s?" % (name, v(g, "купил", "купила"), qn, plural(qn, nf), p, plural(p, RUB), he, v(g, "заплатил", "заплатила"))
        return q, ["Всего %s = <<%s>>%d %s." % (e.split("=")[0], e, r, plural(r, RUB))], r
    if kind == "T3":
        qn, p = num(rnd, 2, 12), num(rnd, 3, 60)
        r1, e1 = calc(qn, "*", p)
        m = num(rnd, r1 + 5, r1 + 400)
        r2, e2 = calc(m, "-", r1)
        q = "У %s было %d %s. %s %s %d %s по %d %s. Сколько рублей у %s осталось?" % (
            gen, m, plural(m, RUB), he.capitalize(), v(g, "купил", "купила"), qn, plural(qn, nf), p, plural(p, RUB), him)
        return q, ["Покупка стоит %s = <<%s>>%d %s." % (e1.split("=")[0], e1, r1, plural(r1, RUB)), "Осталось %s = <<%s>>%d %s." % (e2.split("=")[0], e2, r2, plural(r2, RUB))], r2
    if kind == "T4":
        k, each = rnd.randint(2, 9), num(rnd, 2, 30)
        a = k * each
        r, e = calc(a, "/", k)
        q = "%s %s %d %s поровну в %d %s. Сколько %s в каждой коробке?" % (name, v(g, "разложил", "разложила"), a, plural(a, nf), k, plural(k, ("коробку", "коробки", "коробок")), nf[2])
        return q, ["В каждой коробке %s = <<%s>>%d." % (e.split("=")[0], e, r)], r
    if kind == "T5":
        sp, t = num(rnd, 12, 95), num(rnd, 2, 9)
        r, e = calc(sp, "*", t)
        veh = rnd.choice(("Поезд", "Автобус", "Велосипедист", "Машина"))
        q = "%s едет со скоростью %d км в час. Сколько километров %s проедет за %d %s?" % (veh, sp, "она" if veh == "Машина" else "он", t, plural(t, ("час", "часа", "часов")))
        return q, ["Путь равен %s = <<%s>>%d км." % (e.split("=")[0], e, r)], r
    if kind == "T6":
        name2, _, g2 = rnd.choice([x for x in NAMES_RU if x[0] != name])
        a, b, c = rnd.randint(4, 30), rnd.randint(2, 12), rnd.randint(2, 15)
        r1, e1 = calc(a, "+", b)
        r2, e2 = calc(r1, "+", c)
        Y = ("год", "года", "лет")
        q = "%s %d %s. %s на %d %s старше. Сколько лет будет %s через %d %s?" % (
            name[:-1] + "е", a, plural(a, Y), name2, b, plural(b, Y), name2[:-1] + "е", c, plural(c, Y))
        return q, ["Сейчас %s %s = <<%s>>%d." % (name2[:-1] + "е", e1.split("=")[0], e1, r1), "Через %d %s будет %s = <<%s>>%d." % (c, plural(c, Y), e2.split("=")[0], e2, r2)], r2
    if kind == "T7":
        a, b = num(rnd, 5, 60), num(rnd, 5, 60)
        r1, e1 = calc(a, "+", b)
        c = num(rnd, 2, r1 - 1)
        r2, e2 = calc(r1, "-", c)
        q = "В корзине %d %s и %d %s. Съели %d %s. Сколько фруктов осталось?" % (a, plural(a, ("яблоко", "яблока", "яблок")), b, plural(b, ("груша", "груши", "груш")), c, plural(c, ("фрукт", "фрукта", "фруктов")))
        return q, ["Всего было %s = <<%s>>%d фруктов." % (e1.split("=")[0], e1, r1), "Осталось %s = <<%s>>%d." % (e2.split("=")[0], e2, r2)], r2
    if kind == "T8":   # отложенный вид
        a, k = num(rnd, 5, 60), rnd.randint(2, 5)
        r1, e1 = calc(a, "*", k)
        r2, e2 = calc(a, "+", r1)
        q = "В первый день %s %s %d %s, а во второй — в %d %s больше. Сколько страниц %s %s за два дня?" % (
            name, v(g, "прочитал", "прочитала"), a, plural(a, ("страницу", "страницы", "страниц")), k, plural(k, ("раз", "раза", "раз")), he, v(g, "прочитал", "прочитала"))
        return q, ["Во второй день %s = <<%s>>%d страниц." % (e1.split("=")[0], e1, r1), "За два дня %s = <<%s>>%d." % (e2.split("=")[0], e2, r2)], r2
    if kind == "T9":
        a, w = num(rnd, 5, 50), rnd.randint(2, 6)
        r1, e1 = calc(w, "*", 7)
        r2, e2 = calc(r1, "*", a)
        q = "%s откладывает %d %s в день. Сколько рублей %s отложит за %d %s?" % (name, a, plural(a, RUB), he, w, plural(w, ("неделю", "недели", "недель")))
        return q, ["В %d %s %s = <<%s>>%d %s." % (w, "неделях", e1.split("=")[0], e1, r1, plural(r1, ("день", "дня", "дней"))), "Отложит %s = <<%s>>%d %s." % (e2.split("=")[0], e2, r2, plural(r2, RUB))], r2
    if kind == "T10":
        r, s_ = num(rnd, 3, 25), num(rnd, 5, 30)
        r1, e1 = calc(r, "*", s_)
        o = num(rnd, 2, r1 - 1)
        r2, e2 = calc(r1, "-", o)
        M = ("место", "места", "мест")
        q = "В зале %d %s по %d %s. Занято %d %s. Сколько мест свободно?" % (r, plural(r, ("ряд", "ряда", "рядов")), s_, plural(s_, M), o, plural(o, M))
        return q, ["Всего мест %s = <<%s>>%d." % (e1.split("=")[0], e1, r1), "Свободно %s = <<%s>>%d." % (e2.split("=")[0], e2, r2)], r2
    if kind == "T11":
        a, k = num(rnd, 5, 80), rnd.randint(2, 6)
        r1, e1 = calc(a, "*", k)
        gen2 = rnd.choice([x[1] for x in NAMES_RU if x[0] != name])
        q = "У %s %d %s, а у %s в %d %s больше. Сколько %s у %s?" % (gen, a, plural(a, nf), gen2, k, plural(k, ("раз", "раза", "раз")), nf[2], gen2)
        return q, ["У %s %s = <<%s>>%d." % (gen2, e1.split("=")[0], e1, r1)], r1
    if kind == "T12":  # отложенный вид
        k, gcount = rnd.randint(2, 8), rnd.randint(2, 12)
        a = k * gcount
        r, e = calc(a, "/", k)
        q = "%d %s разделили на группы по %d %s. Сколько групп получилось?" % (a, plural(a, ("ученика", "учеников", "учеников")) if a % 10 != 1 or a % 100 == 11 else "ученика", k, plural(k, ("человеку", "человека", "человек")))
        return q, ["Групп %s = <<%s>>%d." % (e.split("=")[0], e, r)], r
    if kind == "T13":
        nf2 = rnd.choice([x for x in NOUNS_RU if x != nf])
        q1, p1, q2, p2 = num(rnd, 2, 9), num(rnd, 3, 50), num(rnd, 2, 9), num(rnd, 3, 50)
        r1, e1 = calc(q1, "*", p1)
        r2, e2 = calc(q2, "*", p2)
        r3, e3 = calc(r1, "+", r2)
        q = "%s %s %d %s по %d %s и %d %s по %d %s. Сколько рублей %s %s?" % (
            name, v(g, "купил", "купила"), q1, plural(q1, nf), p1, plural(p1, RUB), q2, plural(q2, nf2), p2, plural(p2, RUB), he, v(g, "потратил", "потратила"))
        return q, ["Первая покупка: %s = <<%s>>%d %s." % (e1.split("=")[0], e1, r1, plural(r1, RUB)), "Вторая покупка: %s = <<%s>>%d %s." % (e2.split("=")[0], e2, r2, plural(r2, RUB)),
                   "Всего %s = <<%s>>%d %s." % (e3.split("=")[0], e3, r3, plural(r3, RUB))], r3
    if kind == "T14":  # отложенный вид
        half = num(rnd, 10, 200)
        m = 2 * half
        c = num(rnd, 2, half - 1)
        r1, e1 = calc(m, "/", 2)
        r2, e2 = calc(m, "-", r1)
        r3, e3 = calc(r2, "-", c)
        q = "У %s было %d %s. Половину %s %s на книги, а потом ещё %d %s на ручки. Сколько рублей осталось?" % (
            gen, m, plural(m, RUB), he, v(g, "потратил", "потратила"), c, plural(c, RUB))
        return q, ["На книги ушло %s = <<%s>>%d %s." % (e1.split("=")[0], e1, r1, plural(r1, RUB)), "Осталось %s = <<%s>>%d." % (e2.split("=")[0], e2, r2),
                   "После ручек осталось %s = <<%s>>%d %s." % (e3.split("=")[0], e3, r3, plural(r3, RUB))], r3
    raise ValueError(kind)


def gen_en(kind, rnd):
    name, g = rnd.choice(NAMES_EN)
    nf = rnd.choice(NOUNS_EN)
    he, his = v(g, "he", "she"), v(g, "his", "her")

    def pl(n):
        return nf[0] if n == 1 else nf[1]
    if kind == "T1":
        a, b, c = rnd.randint(12, 90), rnd.randint(2, 11), rnd.randint(2, 30)
        r1, e1 = calc(a, "-", b)
        r2, e2 = calc(r1, "+", c)
        q = "%s had %d %s. %s gave away %d and then bought %d more. How many %s does %s have now?" % (name, a, pl(a), he.capitalize(), b, c, nf[1], name)
        return q, ["After giving away %d, %s had %s = <<%s>>%d." % (b, he, e1.split("=")[0], e1, r1), "Then %s had %s = <<%s>>%d." % (he, e2.split("=")[0], e2, r2)], r2
    if kind == "T2":
        qn, p = rnd.randint(2, 19), rnd.randint(3, 95)
        r, e = calc(qn, "*", p)
        q = "%s bought %d %s for $%d each. How many dollars did %s pay?" % (name, qn, pl(qn), p, he)
        return q, ["In total %s = <<%s>>%d dollars." % (e.split("=")[0], e, r)], r
    if kind == "T3":
        qn, p = rnd.randint(2, 12), rnd.randint(3, 60)
        r1, e1 = calc(qn, "*", p)
        m = rnd.randint(r1 + 5, r1 + 400)
        r2, e2 = calc(m, "-", r1)
        q = "%s had $%d. %s bought %d %s for $%d each. How many dollars does %s have left?" % (name, m, he.capitalize(), qn, pl(qn), p, he)
        return q, ["The purchase costs %s = <<%s>>%d dollars." % (e1.split("=")[0], e1, r1), "Left: %s = <<%s>>%d dollars." % (e2.split("=")[0], e2, r2)], r2
    if kind == "T4":
        k, each = rnd.randint(2, 9), rnd.randint(2, 30)
        a = k * each
        r, e = calc(a, "/", k)
        q = "%s put %d %s equally into %d boxes. How many %s are in each box?" % (name, a, pl(a), k, nf[1])
        return q, ["Each box has %s = <<%s>>%d." % (e.split("=")[0], e, r)], r
    if kind == "T5":
        sp, t = rnd.randint(12, 95), rnd.randint(2, 9)
        r, e = calc(sp, "*", t)
        veh = rnd.choice(("A train", "A bus", "A cyclist", "A car"))
        q = "%s travels at %d km per hour. How many kilometers will it cover in %d hours?" % (veh, sp, t)
        return q, ["The distance is %s = <<%s>>%d km." % (e.split("=")[0], e, r)], r
    if kind == "T6":
        name2, g2 = rnd.choice([x for x in NAMES_EN if x[0] != name])
        a, b, c = rnd.randint(4, 30), rnd.randint(2, 12), rnd.randint(2, 15)
        r1, e1 = calc(a, "+", b)
        r2, e2 = calc(r1, "+", c)
        q = "%s is %d years old. %s is %d years older. How old will %s be in %d years?" % (name, a, name2, b, name2, c)
        return q, ["Now %s is %s = <<%s>>%d." % (name2, e1.split("=")[0], e1, r1), "In %d years: %s = <<%s>>%d." % (c, e2.split("=")[0], e2, r2)], r2
    if kind == "T7":
        a, b = rnd.randint(5, 60), rnd.randint(5, 60)
        r1, e1 = calc(a, "+", b)
        c = rnd.randint(2, r1 - 1)
        r2, e2 = calc(r1, "-", c)
        q = "A basket has %d apples and %d pears. %d fruits were eaten. How many fruits are left?" % (a, b, c)
        return q, ["There were %s = <<%s>>%d fruits." % (e1.split("=")[0], e1, r1), "Left: %s = <<%s>>%d." % (e2.split("=")[0], e2, r2)], r2
    if kind == "T8":
        a, k = rnd.randint(5, 60), rnd.randint(2, 5)
        r1, e1 = calc(a, "*", k)
        r2, e2 = calc(a, "+", r1)
        q = "On the first day %s read %d pages, and on the second day %d times as many. How many pages did %s read in two days?" % (name, a, k, he)
        return q, ["On the second day: %s = <<%s>>%d pages." % (e1.split("=")[0], e1, r1), "In two days: %s = <<%s>>%d." % (e2.split("=")[0], e2, r2)], r2
    if kind == "T9":
        a, w = rnd.randint(5, 50), rnd.randint(2, 6)
        r1, e1 = calc(w, "*", 7)
        r2, e2 = calc(r1, "*", a)
        q = "%s saves $%d a day. How many dollars will %s save in %d weeks?" % (name, a, he, w)
        return q, ["%d weeks are %s = <<%s>>%d days." % (w, e1.split("=")[0], e1, r1), "%s will save %s = <<%s>>%d dollars." % (he.capitalize(), e2.split("=")[0], e2, r2)], r2
    if kind == "T10":
        r, s_ = rnd.randint(3, 25), rnd.randint(5, 30)
        r1, e1 = calc(r, "*", s_)
        o = rnd.randint(2, r1 - 1)
        r2, e2 = calc(r1, "-", o)
        q = "A hall has %d rows of %d seats. %d seats are taken. How many seats are free?" % (r, s_, o)
        return q, ["There are %s = <<%s>>%d seats." % (e1.split("=")[0], e1, r1), "Free: %s = <<%s>>%d." % (e2.split("=")[0], e2, r2)], r2
    if kind == "T11":
        a, k = rnd.randint(5, 80), rnd.randint(2, 6)
        r1, e1 = calc(a, "*", k)
        name2 = rnd.choice([x[0] for x in NAMES_EN if x[0] != name])
        q = "%s has %d %s, and %s has %d times as many. How many %s does %s have?" % (name, a, pl(a), name2, k, nf[1], name2)
        return q, ["%s has %s = <<%s>>%d." % (name2, e1.split("=")[0], e1, r1)], r1
    if kind == "T12":
        k, gcount = rnd.randint(2, 8), rnd.randint(2, 12)
        a = k * gcount
        r, e = calc(a, "/", k)
        q = "%d students were split into groups of %d. How many groups were formed?" % (a, k)
        return q, ["Groups: %s = <<%s>>%d." % (e.split("=")[0], e, r)], r
    if kind == "T13":
        nf2 = rnd.choice([x for x in NOUNS_EN if x != nf])
        q1, p1, q2, p2 = rnd.randint(2, 9), rnd.randint(3, 50), rnd.randint(2, 9), rnd.randint(3, 50)
        r1, e1 = calc(q1, "*", p1)
        r2, e2 = calc(q2, "*", p2)
        r3, e3 = calc(r1, "+", r2)
        q = "%s bought %d %s for $%d each and %d %s for $%d each. How many dollars did %s spend?" % (name, q1, pl(q1), p1, q2, nf2[1], p2, he)
        return q, ["First purchase: %s = <<%s>>%d dollars." % (e1.split("=")[0], e1, r1), "Second purchase: %s = <<%s>>%d dollars." % (e2.split("=")[0], e2, r2),
                   "Total: %s = <<%s>>%d dollars." % (e3.split("=")[0], e3, r3)], r3
    if kind == "T14":
        half = rnd.randint(10, 200)
        m = 2 * half
        c = rnd.randint(2, half - 1)
        r1, e1 = calc(m, "/", 2)
        r2, e2 = calc(m, "-", r1)
        r3, e3 = calc(r2, "-", c)
        q = "%s had $%d. %s spent half on books and then $%d more on pens. How many dollars are left?" % (name, m, he.capitalize(), c)
        return q, ["Books cost %s = <<%s>>%d dollars." % (e1.split("=")[0], e1, r1), "Left: %s = <<%s>>%d." % (e2.split("=")[0], e2, r2),
                   "After the pens: %s = <<%s>>%d dollars." % (e3.split("=")[0], e3, r3)], r3
    raise ValueError(kind)


KINDS = ["T%d" % i for i in range(1, 15)]


def make(kind, lang, rnd):
    q, steps, ans = (gen_ru if lang == "ru" else gen_en)(kind, rnd)
    return {"question": q, "answer": "\n".join(steps) + "\n#### %d" % ans, "вид": kind, "язык": lang}
