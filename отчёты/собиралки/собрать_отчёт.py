# -*- coding: utf-8 -*-
"""Собирает ОТЧЁТ_NNL.html (одна страница, графики — встроенный SVG). Все числа — из замеров v3/v4 и train/STATE.md.
Запуск: python собрать_отчёт.py"""
import math
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ОТЧЁТ_NNL.html")
BG, TX, MUT, GRID, BLUE, ORG, GRN, GRY = "#FAF9F5", "#141413", "#5E5D59", "#D1CFC5", "#6A9BCC", "#EB6834", "#BCD1CA", "#D1CFC5"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def svg(w, h, body):
    return '<svg viewBox="0 0 %d %d" width="100%%" role="img" font-family="inherit">%s</svg>' % (w, h, body)


def text(x, y, s, size=14, fill=TX, anchor="start", weight="400"):
    return '<text x="%s" y="%s" font-size="%s" fill="%s" text-anchor="%s" font-weight="%s">%s</text>' % (x, y, size, fill, anchor, weight, esc(s))


# ---------- 1. размер на лог-шкале + качество (точки) ----------
def chart_scale():
    W, H, L, R, T, B = 900, 330, 70, 30, 30, 60
    pts = [("TINY 1.0", 31878, None, GRY, "расписание инструкций"), ("TINY 1.6", 609753, 0.768, BLUE, "справочник: сеть + память"),
           ("NNL v3", 9485595, 0.731, ORG, "ядро + 3 блока"), ("NNL v4", 8191560, 0.730, ORG, "ядро + 4 области")]
    lo, hi = math.log10(2e4), math.log10(2e7)
    X = lambda v: L + (math.log10(v) - lo) / (hi - lo) * (W - L - R)
    b = ""
    for e in (4, 5, 6, 7):
        for m in ((1, 3) if e < 7 else (1,)):
            v = m * 10 ** e
            if 2e4 <= v <= 2e7:
                b += '<line x1="%s" x2="%s" y1="%s" y2="%s" stroke="%s"/>' % (X(v), X(v), T, H - B, GRID)
                lab = ("%s тыс." % (v // 1000)) if v < 1e6 else ("%s млн" % (v // 10 ** 6))
                b += text(X(v), H - B + 22, lab, 13, MUT, "middle")
    b += '<line x1="%s" x2="%s" y1="%s" y2="%s" stroke="%s"/>' % (L, W - R, H - B, H - B, TX)
    b += text((L + W - R) / 2, H - 12, "число обученных параметров (логарифмическая шкала)", 13, MUT, "middle")
    y0, y1, ylo, yhi = H - B, T + 10, 0.6, 0.85
    Y = lambda q: y0 - (q - ylo) / (yhi - ylo) * (y0 - y1)
    for q in (0.6, 0.7, 0.8):
        b += '<line x1="%s" x2="%s" y1="%s" y2="%s" stroke="%s" stroke-dasharray="3 4"/>' % (L, W - R, Y(q), Y(q), GRID)
        b += text(L - 8, Y(q) + 5, "%.1f" % q, 13, MUT, "end")
    b += text(14, T + 6, "верно, доля", 13, MUT)
    for name, n, q, col, sub in pts:
        x = X(n)
        if q is None:
            b += '<line x1="%s" x2="%s" y1="%s" y2="%s" stroke="%s" stroke-width="2" stroke-dasharray="4 3"/>' % (x, x, T + 8, H - B, col)
            b += text(x + 8, T + 24, name, 14, TX, "start", "700") + text(x + 8, T + 42, sub, 12, MUT)
            b += text(x + 8, T + 60, "другая задача, на этой шкале не измеряется", 12, MUT)
            continue
        b += '<circle cx="%s" cy="%s" r="8" fill="%s" stroke="%s" stroke-width="1"/>' % (x, Y(q), col, TX)
        dy = -16 if name != "NNL v4" else 28
        b += text(x, Y(q) + dy, "%s  %.3f" % (name, q), 14, TX, "middle", "700")
    return svg(W, H, b)


# ---------- 2. качество военкомата: столбцы ----------
def chart_quality():
    rows = [("BM25 + крошка", 0.700, GRY), ("+ своя сеть (первая TINY 1.6)", 0.751, GRY), ("приложение сейчас (сеть + память)", 0.768, BLUE),
            ("NNL v3: разбор → блок области", 0.737, ORG), ("NNL v4: блок «здоровье»", 0.730, ORG)]
    W, H, L, R = 900, 60 + 46 * len(rows), 360, 90
    b = text(L, 22, "здоровье: верный первый ответ на 293 тестовых вопросах (доля)", 13, MUT)
    for i, (name, v, col) in enumerate(rows):
        y = 44 + i * 46
        b += text(L - 10, y + 20, name, 13, TX, "end")
        w = (W - L - R) * (v - 0.5) / 0.3
        b += '<rect x="%s" y="%s" width="%s" height="28" fill="%s" stroke="%s"/>' % (L, y, w, col, TX)
        b += text(L + w + 8, y + 20, "%.3f" % v, 14, TX, "start", "700")
    b += '<line x1="%s" x2="%s" y1="36" y2="%s" stroke="%s"/>' % (L, L, H - 8, TX)
    b += text(L, H - 2, "шкала начинается с 0,5", 12, MUT)
    return svg(W, H, b)


# ---------- 3. контроль: «светофор» из чисел ----------
def tiles():
    items = [("0,4 %", "ответов старых областей изменились после вставки новой", "вставка"),
             ("99–100 %", "вопросов вынутой области получили «не знаю»", "снятие"),
             ("0 из 7 023", "проверок целостности нарушено (40 случайных вставок/снятий)", "целостность"),
             ("0 файлов", "изменено или потеряно после всех шагов (31 файл, sha256)", "данные"),
             ("12 180 / 12 180", "ответов с записью следа: какие блоки ответили", "след"),
             ("6,5 %", "вопросов уходят к соседу, если снять и «заявку» области (предел)", "слабое место")]
    h = ""
    for big, small, tag in items:
        col = ORG if tag == "слабое место" else BLUE
        h += '<div class="tile" style="border-top:4px solid %s"><div class="big">%s</div><div class="sm">%s</div><div class="tag">%s</div></div>' % (col, big, small, tag)
    return '<div class="tiles">%s</div>' % h


# ---------- 4. задачи: столбцы ----------
def chart_tasks():
    rows = [("свои задачи, знакомые слова", 0.92, 0.95), ("свои задачи, новые слова", 0.18, 0.28), ("другой генератор задач", 0.55, 0.58),
            ("школьные задачи GSM8K / MGSM", 0.01, 0.02)]
    W, H, L = 900, 70 + 54 * len(rows), 270
    b = text(L, 20, "блок «задачи»: доля верных ответов", 13, MUT)
    b += '<rect x="%s" y="30" width="14" height="14" fill="%s" stroke="%s"/>' % (L, GRN, TX) + text(L + 20, 42, "малый, 1,4 млн", 12, MUT)
    b += '<rect x="%s" y="30" width="14" height="14" fill="%s" stroke="%s"/>' % (L + 150, BLUE, TX) + text(L + 170, 42, "большой, 5,9 млн", 12, MUT)
    for i, (name, small, big) in enumerate(rows):
        y = 58 + i * 54
        b += text(L - 10, y + 28, name, 13, TX, "end")
        for j, (v, col) in enumerate(((small, GRN), (big, BLUE))):
            w = max(2, (W - L - 70) * v)
            b += '<rect x="%s" y="%s" width="%s" height="20" fill="%s" stroke="%s"/>' % (L, y + j * 22, w, col, TX)
            b += text(L + w + 8, y + 15 + j * 22, "%.2f" % v, 13, TX, "start", "700")
    return svg(W, H, b)


# ---------- 5. схема системы ----------
def chart_arch():
    W, H = 900, 400
    b = ""

    def box(x, y, w, h, label, sub="", col=BG, bold=False):
        s = '<rect x="%s" y="%s" width="%s" height="%s" rx="4" fill="%s" stroke="%s" stroke-width="%s"/>' % (x, y, w, h, col, TX, 2 if bold else 1)
        s += text(x + w / 2, y + h / 2 + (0 if not sub else -2), label, 14, TX, "middle", "700" if bold else "400")
        if sub:
            s += text(x + w / 2, y + h / 2 + 16, sub, 11, MUT, "middle")
        return s
    b += box(20, 170, 130, 60, "вопрос человека", "", BG)
    b += '<rect x="210" y="140" width="250" height="120" rx="4" fill="#DFE6EB" stroke="%s" stroke-width="2"/>' % TX
    b += text(335, 166, "ЯДРО", 15, TX, "middle", "700") + text(335, 184, "обычный код, 0 обученных чисел", 11, MUT, "middle")
    b += text(335, 208, "типы · заявки · маршрут", 12, TX, "middle") + text(335, 226, "след · «не знаю»", 12, TX, "middle") + text(335, 244, "заморозка · дообучение одного", 12, TX, "middle")
    b += '<line x1="150" y1="200" x2="210" y2="200" stroke="%s" stroke-width="2"/>' % TX
    areas = [("здоровье", 1.6), ("право", 1.6), ("команды", 1.6), ("задачи", 1.4)]
    for i, (n, m) in enumerate(areas):
        y = 24 + i * 90
        b += '<line x1="460" y1="200" x2="540" y2="%s" stroke="%s"/>' % (y + 28, TX)
        b += box(540, y, 120, 56, n + ".заявка", "0,5 млн: «моё?»", GRN)
        b += '<line x1="660" y1="%s" x2="700" y2="%s" stroke="%s" stroke-width="2"/>' % (y + 28, y + 28, TX)
        b += box(700, y, 180, 56, n, "%s млн: знание" % str(m).replace(".", ","), BLUE)
    b += '<line x1="790" y1="%s" x2="790" y2="%s" stroke="%s" stroke-dasharray="5 4"/>' % (24 + 3 * 90 + 56, 392, ORG)
    b += text(450, 392, "вынул блок «знание» → заявка остаётся → ядро честно говорит «не знаю»", 12, ORG, "middle")
    return svg(W, H, b)


# ---------- 6. временная шкала ----------
def chart_timeline():
    W, H = 900, 270
    steps = [("TINY 1.0", "32 тыс.", "ИИ предлагает порядок,\nточный код проверяет.\n284 из 300 расписаний —\nлучшие возможные", GRY),
             ("TINY 1.6", "0,6 млн", "справочник призывника:\nсеть + память фраз,\nверно 0,768,\nбез чужих весов", BLUE),
             ("NNL v3", "9,5 млн", "ядро без ИИ,\nблоки обучены порознь,\nпроверки К1–К4 пройдены", ORG),
             ("NNL v4", "8,2 млн", "общее ядро, вставка области\nменяет 0,4 %, блок пишет\nтекст (задачи)", ORG),
             ("дальше", "~10 млн+", "блоки приложения\nвнутри ядра, общий язык,\nответы на стыке областей", GRY)]
    n = len(steps)
    b = '<line x1="50" y1="70" x2="%s" y2="70" stroke="%s" stroke-width="3"/>' % (W - 40, TX)
    for i, (name, size, desc, col) in enumerate(steps):
        x = 90 + i * (W - 180) / (n - 1)
        b += '<circle cx="%s" cy="70" r="11" fill="%s" stroke="%s" stroke-width="2"%s/>' % (x, col, TX, ' stroke-dasharray="3 2"' if name == "дальше" else "")
        b += text(x, 40, name, 16, TX, "middle", "700") + text(x, 108, size, 14, MUT, "middle")
        for j, ln in enumerate(desc.split("\n")):
            b += text(x, 140 + j * 18, ln, 12, TX if name != "дальше" else MUT, "middle")
    return svg(W, H, b)


CSS = """
:root{--bg:%s;--tx:%s;--mut:%s;--grid:%s;--blue:%s;--org:%s}
html{color-scheme:light}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.55 "Segoe UI",system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 80px} h1{font:600 34px/1.2 Georgia,serif;margin:0 0 8px}
h2{font:600 24px/1.3 Georgia,serif;margin:48px 0 6px} .lead{color:var(--mut);margin:0 0 24px} .cap{color:var(--mut);font-size:13px;font-style:italic;margin:6px 0 0}
section{border-top:1px solid var(--grid);padding-top:8px} table{border-collapse:collapse;width:100%%;margin:12px 0;font-size:15px}
th,td{border:1px solid var(--tx);padding:8px 10px;text-align:left;vertical-align:top} th{font-weight:700} td.b{background:#DFE6EB;color:#141413;font-weight:700}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:12px 0}
.tile{border:1px solid var(--grid);padding:12px 14px;background:rgba(255,255,255,.35)} .big{font:600 28px Georgia,serif}
.sm{color:var(--mut);font-size:14px} .tag{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);margin-top:6px}
.note{border-left:4px solid var(--org);padding:6px 14px;margin:14px 0;background:rgba(235,104,52,.07)} ul{padding-left:20px}
@media(max-width:560px){h1{font-size:26px} .big{font-size:22px}}
""" % (BG, TX, MUT, GRID, BLUE, ORG)

HTML = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NNL: отчёт</title><style>@@css@@</style></head><body><main>
<h1>От маленькой сети к ядру с блоками</h1>
<p class="lead">TINY 1.0 → TINY 1.6 → NNL v3 → NNL v4. Первые прогоны, цифры наши, на нашем железе (ноутбук, без GPU). 7–8 октября 2026.</p>

<section><h2>1. Путь по размеру и качеству</h2>
<p class="lead">Что росло: размер — с 32 тысяч до 8–9 миллионов чисел. Что менялось главное: сначала «умеет ли сеть», потом «можно ли ею управлять».</p>
@@scale@@
<p class="cap">Качество — верный первый ответ на тесте «здоровье». TINY 1.0 решает другую задачу (расписание инструкций), поэтому у неё линия, а не точка.</p></section>

<section><h2>2. Где мы сейчас по точности: честно</h2>
@@quality@@
<p class="cap">Один и тот же тест из 293 вопросов. Цифры приложения — из train/STATE.md; NNL — свои замеры (v3 и v4).</p>
<div class="note"><b>Вывод:</b> по точности NNL <b>не круче</b> приложения: на 3–4 пункта слабее. Блоки NNL — такой же мешок слов с линейным слоем; память фраз и уточняющие вопросы остались в приложении. Отрицание («у меня нет астмы») не понимает ни приложение, ни NNL — проверено.</div></section>

<section><h2>3. В чём NNL круче: управляемость</h2>
<p class="lead">Мини-бенчмарк контроля: вставка и снятие блоков в случайном порядке.</p>
@@tiles@@
<table><tr><th></th><th>приложение (TINY 1.6)</th><th>NNL v4</th></tr>
<tr><td>Знание одной области лежит отдельно, его можно вынуть</td><td>нет: одна сеть на 88 статей</td><td class="b">да</td></tr>
<tr><td>Вставить новую область, не трогая старые</td><td>нет, переобучение сети</td><td class="b">да: 0,4 % изменений</td></tr>
<tr><td>След: какие числа ответили</td><td>частично (источник статьи)</td><td class="b">да, на каждый ответ</td></tr>
<tr><td>Дообучить одну область, остальные не меняются</td><td>нет</td><td class="b">да, файлы остальных побайтно те же</td></tr>
<tr><td>Видеть дыру: в какой области ошибки</td><td>по таблице теста</td><td class="b">по областям и по блокам</td></tr>
<tr><td>Точность на «здоровье»</td><td class="b">0,768</td><td>0,730</td></tr></table>
<p class="cap">Строки про приложение — по train/STATE.md, не проверялись отдельно в этой сессии.</p></section>

<section><h2>4. Как устроена система</h2>
@@arch@@
<p class="cap">Область = «заявка» (маленькая, знает, какие вопросы её) + «знание». Вынули знание — заявка остаётся, и дыра видна по имени.</p></section>

<section><h2>5. Блок, который пишет текст (задачи)</h2>
@@tasks@@
<p class="cap">Блок решает задачи по шагам, и ядро пересчитывает каждый шаг. Он выучил шаблоны, но не язык: новые слова — 18–28 %. Размер в 4 раза не помог: не хватает разнообразия текстов, а не параметров.</p></section>

<section><h2>6. Развитие и что дальше</h2>
@@timeline@@
<h3>Что известно</h3><ul>
<li>Ядро без ИИ управляет блоками: вставка, снятие, след, «не знаю», заморозка. Проверено на 12 180 ответах.</li>
<li>Блоки разных видов живут вместе: выбирающий ответ и пишущий текст.</li>
<li>Знание области можно вынуть, остальные области при этом не меняются.</li></ul>
<h3>Что ещё не доказано (главные риски)</h3><ul>
<li><b>Качество не потеряется?</b> Нужно поставить в блоки сеть и память из приложения и проверить на реальных фразах людей.</li>
<li><b>Вопросы на стыке областей</b> («астма и отсрочка»): сейчас вопрос идёт в один блок.</li>
<li><b>Рассуждение текстом</b> на миллионах чисел слабо; нужен общий блок «язык» и много разных формулировок от учителя (Claude).</li>
<li><b>Масштаб:</b> проверены 4 области. Гипотеза — 30+ областей, не проверена.</li></ul>
<h3>Порядок работ</h3><table><tr><th>шаг</th><th>что</th><th>успех</th></tr>
<tr><td>1</td><td>блоки приложения (сеть, память, обработка отрицаний) внутри ядра, проверка на реальных фразах</td><td>качество не хуже 0,768, контроль сохранён</td></tr>
<tr><td>2</td><td>вопросы на стыке двух областей</td><td>ядро вызывает два блока, след показывает оба</td></tr>
<tr><td>3</td><td>общий блок «язык» + блоки знаний поверх</td><td>новые формулировки задач ≥ 0,5</td></tr>
<tr><td>4</td><td>10 областей, бюджет ~10 млн</td><td>вставка новой не меняет старые &gt; 2 %</td></tr></table></section>
</main></body></html>"""


def main():
    html = HTML
    for k, v in {"css": CSS, "scale": chart_scale(), "quality": chart_quality(), "tiles": tiles(), "arch": chart_arch(), "tasks": chart_tasks(), "timeline": chart_timeline()}.items():
        html = html.replace("@@%s@@" % k, v)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("записан", OUT, len(html) // 1024, "КБ")


if __name__ == "__main__":
    main()
