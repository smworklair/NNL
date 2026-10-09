# -*- coding: utf-8 -*-
"""Презентация композиции: три сущности, покой без запроса, два порядка.
Строит v9/результаты/ЯП_презентация.html. Запуск: python построить_презентацию_яп.py"""
import os

V9 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
РЕЗ = os.path.join(V9, "результаты")
OUT = os.path.join(РЕЗ, "ЯП_презентация.html")

BG, TX, MUT, GRID = "#101014", "#F2F2F5", "#A9A9B5", "#2C2C38"
BOX, BUS, ACC = "#23234D", "#9D9DF5", "#EB6834"
LIN = "#C9C9E8"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def svg(w, h, body):
    return '<svg viewBox="0 0 %d %d" width="100%%" role="img" font-family="inherit">%s</svg>' % (w, h, body)


def text(x, y, s, size=14, fill=TX, anchor="start", weight="400"):
    return '<text x="%s" y="%s" font-size="%s" fill="%s" text-anchor="%s" font-weight="%s">%s</text>' % (x, y, size, fill, anchor, weight, esc(s))


def box(x, y, w, h, title, subs=None, fill=BOX, tcol=TX, bold=True, dash=False, op=1.0):
    s = '<rect x="%s" y="%s" width="%s" height="%s" rx="10" fill="%s" stroke="%s" stroke-width="1.5"%s opacity="%s"/>' % (
        x, y, w, h, fill, LIN, ' stroke-dasharray="7 5"' if dash else "", op)
    subs = subs or []
    ty = y + h / 2 - 9 * len(subs) + 5
    s += text(x + w / 2, ty, title, 14, tcol, "middle", "700" if bold else "400")
    for i, ln in enumerate(subs):
        s += text(x + w / 2, ty + 19 + i * 16, ln, 11.5, MUT, "middle")
    return s


def arrow(x1, y1, x2, y2, col=LIN, dash=False, w=2):
    return '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s" marker-end="url(#a)"%s/>' % (
        x1, y1, x2, y2, col, w, ' stroke-dasharray="6 5"' if dash else "")


DEFS = '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="%s"/></marker></defs>' % LIN


def d_покой():
    b = DEFS
    b += box(180, 10, 300, 56, "ЯДРО-держатель", ["реестр: кто воткнут"], BOX)
    b += arrow(330, 66, 330, 92)
    b += '<rect x="120" y="92" width="420" height="200" rx="10" fill="none" stroke="%s" stroke-width="1.5" stroke-dasharray="7 5"/>' % LIN
    b += text(132, 112, "ПРОЗРАЧНОСТЬ (среда)", 12, MUT)
    b += text(132, 130, "природа: свести · преломить · знаний: ноль", 11, MUT)
    for i, n in enumerate(("медицина", "расписание", "право")):
        x = 132 + i * 138
        b += box(x, 145, 128, 60, "○ " + n, ["воткнут", "молчит"], BOX)
        b += arrow(196 + i * 138, 145, 196 + i * 138, 132)
    b += text(330, 240, "держание сверху вниз:", 12, MUT, "middle")
    b += text(330, 260, "ядро держит среду · среда держит блоки", 12, LIN, "middle")
    b += text(330, 282, "тока нет · целое уже есть", 12, LIN, "middle")
    return svg(660, 300, b)


def d_лучи():
    b = DEFS
    for i, n in enumerate(("медицина", "расписание", "право")):
        x = 30 + i * 150
        b += box(x, 20, 130, 52, n, ["светит"], BOX)
        b += arrow(x + 65, 72, 225, 130)
    b += text(225, 148, "ТОЧКА: трое стали одним", 12, LIN, "middle")
    b += arrow(225, 130, 225, 165)
    b += '<rect x="150" y="165" width="150" height="46" rx="23" fill="%s"/>' % BUS
    b += text(225, 193, "прозрачность", 13, "#101014", "middle", "700")
    b += text(225, 232, "обрабатывает единый луч", 12, MUT, "middle")
    b += text(225, 252, "течение снизу вверх:", 12, MUT, "middle")
    b += text(225, 270, "блоки → среда", 12, LIN, "middle")
    return svg(480, 280, b)


def d_два_порядка():
    b = DEFS
    b += arrow(120, 30, 120, 120)
    b += text(130, 60, "ДЕРЖАНИЕ: сверху вниз", 13, TX)
    b += text(130, 82, "ядро → среда → блоки", 12, MUT)
    b += text(130, 104, "(розетка держит вилку)", 12, MUT)
    b += arrow(420, 120, 420, 30)
    b += text(430, 60, "ТЕЧЕНИЕ: снизу вверх", 13, TX)
    b += text(430, 82, "блоки → среда", 12, MUT)
    b += text(430, 104, "(ток из вилки в розетку)", 12, MUT)
    b += text(300, 150, "встречаются в среде", 13, LIN, "middle", "700")
    return svg(600, 165, b)


CSS = """
*{box-sizing:border-box} body{margin:0;background:%s;color:%s;font:16px/1.55 "Segoe UI",system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 80px} h1{font:600 32px/1.2 Georgia,serif;margin:0 0 8px}
h2{font:600 24px/1.3 Georgia,serif;margin:40px 0 6px} .lead{color:%s;margin:0 0 20px}
.kpi{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0} .kpi div{border:1px solid %s;padding:10px 16px;min-width:140px;background:#17171F}
.kpi b{display:block;font:600 26px Georgia,serif} .kpi span{color:%s;font-size:13px}
table{border-collapse:collapse;width:100%%;margin:12px 0;font-size:15px} th,td{border:1px solid %s;padding:8px 10px;text-align:left;vertical-align:top}
.cap{color:%s;font-size:13px;font-style:italic} .note{border-left:4px solid %s;padding:6px 14px;margin:14px 0;background:rgba(235,104,52,.1)}
.check li{margin:6px 0} section{border-top:1px solid %s;padding-top:8px}
""" % (BG, TX, MUT, GRID, MUT, GRID, MUT, ACC, GRID)

HTML = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Композиция: ядро · среда · блоки</title><style>@@css@@</style></head><body><main>
<h1>Композиция: ядро · среда · блоки</h1>
<p class="lead">Три сущности. Блоки — лучи со знаниями. Среда (прозрачность) — сводит и преломляет, знаний ноль, не учится. Ядро — держит и учитывает, мнения нет. Композиция существует уже в покое, без запросов.</p>
<div class="kpi">
<div><b>3</b><span>сущности, не две и не одна</span></div>
<div><b>0</b><span>знаний в среде</span></div>
<div><b>0</b><span>мнений у ядра</span></div>
<div><b>0</b><span>выборов «кто отвечает»</span></div>
<div><b>0</b><span>переучиваний при вставке/снятии</span></div>
<div><b>1</b><span>целое уже в покое</span></div>
</div>

<section><h2>1. Покой: целое уже есть</h2>@@покой@@
<p class="cap">Ничего не течёт, никто не отвечает. Композиция — само воткнутое состояние: реестр указывает на блоки, у каждого заранее объявлено место в общем поле, у среды заранее объявлено, как места сводятся. Как вилки в розетке: тока нет, circuit собран.</p></section>

<section><h2>2. Два порядка — оба верные</h2>@@порядки@@
<p class="cap">В покое сверху вниз: ядро держит среду, среда держит блоки. Когда светят — снизу вверх: блоки светят в среду. Встречаются в среде: она и гнездо, и приёмник.</p></section>

<section><h2>3. Лучи: трое → один → обработка</h2>@@лучи@@
<p class="cap">Три луча сходятся в точку — дальше летит один луч. Он втыкается в прозрачность, она его обрабатывает. Кристалл — десятки таких отражений: луч мечется от стенки к стенке, каждый раз меняясь.</p></section>

<section><h2>4. Три сущности — кто что</h2>
<table><tr><th></th><th>что это</th><th>знания</th><th>учёба</th><th>вставка/снятие</th></tr>
<tr><td><b>Блоки</b></td><td>лучи-коннекторы: знания своей области</td><td>только здесь</td><td>каждый свой переводчик</td><td>воткнул — умнее; вынул — как было</td></tr>
<tr><td><b>Среда</b></td><td>прозрачность: свести · преломить</td><td>ноль</td><td>никогда</td><td>не трогается вообще</td></tr>
<tr><td><b>Ядро</b></td><td>держатель: реестр, запуск, след</td><td>ноль</td><td>никогда</td><td>вычеркнул/вписал строку</td></tr></table>
<div class="note"><b>Почему не ядро и не выученный параметр:</b> у ядра со мнением дохнет вынимание без потерь; выученное мнение надо переучивать при каждой вставке — та самая спайка-халтура. Среда — параметр формы (шлифовка линзы), а не знания.</div></section>

<section><h2>5. Природа среды (фиксирована, не учится)</h2>
<table><tr><th>элемент формы</th><th>пример</th></tr>
<tr><td>Размер общего поля</td><td>N чисел — место, куда пишут все</td></tr>
<tr><td>Формула сведения</td><td>среднее с весами / сумма поправок</td></tr>
<tr><td>Правило преобразования</td><td>сжатие, нормировка — как преломление</td></tr>
<tr><td>Круги и остановка</td><td>сколько отражений, когда хватит, бюджет</td></tr></table></section>

<section><h2>6. Думать дальше (открыто)</h2>
<div class="note"><ul>
<li>Кто сводит лучи в точку — сами целятся или линза среды фокусирует?</li>
<li>Сколько отражений и кто решает порядок стенок?</li>
<li>Что среда делает с единым лучом после сведения?</li>
<li>Масштаб: одна среда на миллионы или иерархия сред?</li>
<li>Критерии целого: снятие не трогает остальных; коннектор без среды — мусор; целое решает то, чего нет ни у одного.</li>
</ul></div></section>

<section><h2>7. Что нужно, чтобы построить</h2>
<table><tr><th>нужно</th><th>что именно</th></tr>
<tr><td>Стандарт среды</td><td>файл: размер поля, сведение, преобразование, круги, бюджет</td></tr>
<tr><td>Протокол коннектора</td><td>паспорт: имя, версия, хеш, что пишет/читает, контрольные примеры</td></tr>
<tr><td>Держатель</td><td>подключить (проверки) · вынуть · запустить круги · след</td></tr>
<tr><td>Данные</td><td>пул3 + фразы уже есть; калибровочный набор отдельно от проверочного</td></tr>
<tr><td>Железо</td><td>ноутбук без GPU</td></tr></table>
<div class="note"><b>Чего НЕ делать:</b> выбор отвечающего блока, обучаемый роутер, спайка дообучением всех вместе, учёба на проверочных наборах.</div></section>
</main></body></html>"""

HTML = HTML.replace("@@css@@", CSS).replace("@@покой@@", d_покой()).replace("@@порядки@@", d_два_порядка()).replace("@@лучи@@", d_лучи())


def main():
    os.makedirs(РЕЗ, exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(HTML)
    print("записано", OUT)


if __name__ == "__main__":
    main()
