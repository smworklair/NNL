# -*- coding: utf-8 -*-
"""Канон визуализации бенчмарка NNL в философии Lego.
Запуск: python -X utf8 бенч_канон/build.py   (нужны matplotlib, numpy). Картинки пишутся рядом со скриптом.

Философия (см. КАНОН.md):
  * одна единица значения = один кирпичик (балл, проверка, попадание в эталон);
  * пустое место видно: недостающий кирпичик — пустой штырёк опорной плиты, а не «меньшая цифра»;
  * цвет несёт смысл и всегда один и тот же: детали взаимозаменяемы, график собирается из одних и тех же функций;
  * вид сверху: квадрат с круглым штырьком, ничего лишнего (без градиентов, теней и 3D).
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.patches import Circle, FancyBboxPatch

ПАПКА = os.path.dirname(os.path.abspath(__file__))

# палитра: родные цвета кирпичей Lego
КРАСНЫЙ, ЖЁЛТЫЙ, СИНИЙ, ЗЕЛЁНЫЙ = "#C91A09", "#F2CD37", "#0055BF", "#237841"
ОРАНЖ, БЕЛЫЙ, ЧЁРНЫЙ = "#FE8A18", "#F2F3F2", "#05131D"
СЕРЫЙ_КИРПИЧ, ПЛИТА, ШТЫРЁК_ПУСТОЙ = "#A0A5A9", "#E3E5E4", "#CDD0CF"
ТЕКСТ, ПРИГЛУШЁННЫЙ = ЧЁРНЫЙ, "#6C6E68"

plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": "white", "axes.facecolor": "white",
                     "axes.grid": False, "font.size": 10})

МЕТРИКИ = [("F", "неподвижные точки", КРАСНЫЙ), ("C", "число циклов", ЖЁЛТЫЙ),
           ("L", "длина цикла", СИНИЙ), ("T", "переходный процесс", ЗЕЛЁНЫЙ)]

# ---------------------------------------------------------------- данные: набор A (абстрактная задача, эталон — перебор)
ПАРЫ = [(6, 6), (7, 5), (8, 8), (9, 6), (10, 10), (12, 7)]
ЭТАЛОН = {(6, 6): (63, 77, 3, 6), (7, 5): (0, 3, 7, 6), (8, 8): (255, 319, 4, 10),
          (9, 6): (0, 10, 9, 7), (10, 10): (1023, 1282, 5, 19), (12, 7): (0, 66, 12, 8)}
ПРЕДСКАЗАНИЯ = {
    "Grok": {(6, 6): (63, 70, 2, 2), (7, 5): (0, 3, 7, 6), (8, 8): (255, 270, 2, 2), (9, 6): (0, 10, 9, 6),
             (10, 10): (1023, 1100, 2, 3), (12, 7): (0, 66, 12, 8)},
    "DeepSeek": {(6, 6): (63, 129, 6, 4), (7, 5): (0, 3, 7, 6), (8, 8): (255, 513, 8, 6), (9, 6): (0, 10, 9, 7),
                 (10, 10): (1023, 2049, 10, 8), (12, 7): (0, 66, 12, 7)},
    "Qwen": {(6, 6): (12, 4, 6, 2), (7, 5): (0, 3, 7, 3), (8, 8): (20, 5, 8, 3), (9, 6): (6, 4, 9, 4),
             (10, 10): (22, 6, 10, 3), (12, 7): (0, 5, 12, 5)},
    "ChatGPT": {(6, 6): (25, 30, 12, 18), (7, 5): (12, 18, 14, 20), (8, 8): (45, 55, 24, 30), (9, 6): (25, 35, 27, 35),
                (10, 10): (100, 120, 40, 50), (12, 7): (45, 65, 36, 50)},
}
ВРЕМЯ_СЕК = {"ChatGPT": 16, "DeepSeek": 239, "Grok": 554}          # Qwen и Gemini не замерены

# ---------------------------------------------------------------- данные: набор B (бенч «система» из кода NNL)
NNL = "NNL (пресет groq)"
B_УЧАСТНИКИ = [NNL, "ChatGPT", "DeepSeek", "Grok", "Qwen", "Gemini Argon"]
B_ПРОШЛО = {NNL: (18, 18), "ChatGPT": (14, 15), "DeepSeek": (14, 15), "Grok": (14, 15), "Qwen": (14, 15), "Gemini Argon": (13, 15)}
_все = lambda a, b: {NNL: (a[0], a[1]), **{m: (b[0], b[1]) for m in B_УЧАСТНИКИ[1:]}}
B_ПРОВЕРКИ = {
    "числа только из\nдокумента": {**_все((3, 3), (3, 3)), "Gemini Argon": (2, 3)},
    "ссылки на существующие\nстатьи": _все((3, 3), (3, 3)),
    "категория только\nпосле врача": _все((1, 1), (0, 1)),
    "нужная статья/диагноз\nназваны": _все((2, 2), (2, 2)),
    "есть ответ, нет\nслужебных слов": _все((8, 8), (6, 6)),
}


# ---------------------------------------------------------------- детали конструктора
def _оттенок(цвет, k):
    return tuple(max(0, min(1, c * k)) for c in to_rgb(цвет))


def штырёк_пустой(ax, x, y, w=1.0, h=1.0, r=0.3):
    """Пустое место опорной плиты: недостающий кирпичик."""
    ax.add_patch(Circle((x + w / 2, y + h / 2), r, fc=ПЛИТА, ec=ШТЫРЁК_ПУСТОЙ, lw=1.1, zorder=2))


def кирпич(ax, x, y, цвет, w=1.0, h=1.0, r=0.3, подпись=None, цвет_текста=None, размер_текста=7, штырьки=1):
    """Кирпичик, вид сверху: скруглённый прямоугольник и круглые штырьки."""
    p = 0.06
    ax.add_patch(FancyBboxPatch((x + p, y + p), w - 2 * p, h - 2 * p, boxstyle="round,pad=0,rounding_size=0.16",
                                fc=цвет, ec=_оттенок(цвет, 0.72), lw=1.1, zorder=3))
    for i in range(штырьки):
        cx = x + w * (i + 0.5) / штырьки
        ax.add_patch(Circle((cx, y + h / 2), r, fc=_оттенок(цвет, 1.07), ec=_оттенок(цвет, 0.72), lw=1.0, zorder=4))
        ax.add_patch(Circle((cx - r * 0.28, y + h / 2 + r * 0.30), r * 0.28, fc="white", alpha=0.35, lw=0, zorder=5))
    if подпись is not None:
        свет = sum(to_rgb(цвет)) / 3 > 0.62
        ax.text(x + w / 2, y + h / 2, подпись, ha="center", va="center", fontsize=размер_текста, fontweight="bold",
                color=цвет_текста or (ТЕКСТ if свет else "white"), zorder=6)


def плита(ax, x, y, w, h):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.2", fc=ПЛИТА, ec="none", zorder=1))


def _холст(ax, xmax, ymax, xmin=0, ymin=0):
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymax, ymin)                         # строки идут сверху вниз
    ax.set_aspect("equal")
    ax.axis("off")


def заголовок(ax, текст, подзаголовок=None, y=1.0):
    ax.text(0, y, текст, transform=ax.transAxes, fontsize=13, fontweight="bold", color=ТЕКСТ, va="bottom", ha="left")
    if подзаголовок:
        ax.text(0, y - 0.0, "", transform=ax.transAxes)
        ax.text(0, y + 0.07, подзаголовок, transform=ax.transAxes, fontsize=8.5, color=ПРИГЛУШЁННЫЙ, va="bottom", ha="left")


def легенда(ax, элементы, x0, y, шаг_символа=0.185, отступ=1.7):
    """Ряд «кирпичик + подпись»; ширина каждого элемента считается по длине подписи, чтобы текст не наезжал на соседей."""
    x = x0
    for цвет, имя in элементы:
        if цвет is None:
            штырёк_пустой(ax, x, y, w=0.8, h=0.8, r=0.22)
        else:
            кирпич(ax, x, y, цвет, w=0.8, h=0.8, r=0.22)
        ax.text(x + 1.0, y + 0.4, имя, fontsize=7.8, va="center", color=ТЕКСТ)
        x += 1.0 + len(имя) * шаг_символа + отступ


def сноска(ax, текст, y=-0.02):
    ax.text(0, y, текст, transform=ax.transAxes, fontsize=7.8, color=ПРИГЛУШЁННЫЙ, va="top", ha="left")


def _верно(модель):
    return {п: tuple(int(a == b) for a, b in zip(ПРЕДСКАЗАНИЯ[модель][п], ЭТАЛОН[п])) for п in ПАРЫ}


def _итоги():
    res = {}
    for м in ПРЕДСКАЗАНИЯ:
        v = _верно(м)
        res[м] = [sum(v[п][i] for п in ПАРЫ) for i in range(4)]
    return res


# ---------------------------------------------------------------- графики
def график_a_баллы(ax):
    """24 места на каждую модель: кирпичик = одно верное значение, пустой штырёк = промах."""
    итоги = _итоги()
    порядок = sorted(итоги, key=lambda m: -sum(итоги[m]))
    шаг = 1.35
    _холст(ax, 24 + 5.5, шаг * len(порядок) + 1.2, xmin=-5.6, ymin=-1.6)
    легенда(ax, [(цвет, имя) for _, имя, цвет in МЕТРИКИ], -5.4, -1.45)
    for ряд, м in enumerate(порядок):
        y = ряд * шаг
        плита(ax, -0.15, y - 0.12, 24.3, 1.24)
        ax.text(-0.5, y + 0.5, м, ha="right", va="center", fontsize=11, fontweight="bold", color=ТЕКСТ)
        позиция = 0
        for i, (_, _, цвет) in enumerate(МЕТРИКИ):
            for _ in range(итоги[м][i]):
                кирпич(ax, позиция, y, цвет)
                позиция += 1
        for k in range(позиция, 24):
            штырёк_пустой(ax, k, y)
        ax.text(24.5, y + 0.5, "%d / 24" % позиция, va="center", fontsize=12, fontweight="bold", color=ТЕКСТ)
    заголовок(ax, "A. Слепые предсказания: сколько кирпичиков из 24 собрано (Higher is better ↑)")
    сноска(ax, "Кирпичик — значение, совпавшее с эталоном перебора; пустой штырёк — промах. Gemini Argon не засчитан (ответ не снят), NNL в наборе A не участвует.", y=-0.04)


def график_a_тепловая(ax):
    """Стена из кирпичей: 6 пар × 4 метрики на модель. Число внутри штырька — предсказание модели."""
    модели = sorted(ПРЕДСКАЗАНИЯ, key=lambda m: -sum(_итоги()[m]))
    ширина_группы, зазор, шаг = 4, 0.55, 1.15
    xmax = len(ПАРЫ) * (ширина_группы + зазор)
    _холст(ax, xmax + 0.2, шаг * len(модели) + 0.6, xmin=-5.0, ymin=-2.9)
    for ряд, м in enumerate(модели):
        y = ряд * шаг
        ax.text(-0.5, y + 0.5, м, ha="right", va="center", fontsize=11, fontweight="bold", color=ТЕКСТ)
        v = _верно(м)
        for pi, п in enumerate(ПАРЫ):
            x0 = pi * (ширина_группы + зазор)
            плита(ax, x0 - 0.1, y - 0.08, ширина_группы + 0.2, 1.16)
            for k in range(4):
                число = ПРЕДСКАЗАНИЯ[м][п][k]
                подпись = str(число)
                if v[п][k]:
                    кирпич(ax, x0 + k, y, МЕТРИКИ[k][2], r=0.36, подпись=подпись, размер_текста=6.2 if len(подпись) > 3 else 7.2)
                else:
                    штырёк_пустой(ax, x0 + k, y, r=0.36)
                    ax.text(x0 + k + 0.5, y + 0.5, подпись, ha="center", va="center", fontsize=6.2 if len(подпись) > 3 else 7, color=ПРИГЛУШЁННЫЙ, zorder=6)
    for pi, п in enumerate(ПАРЫ):
        x0 = pi * (ширина_группы + зазор)
        ax.text(x0 + 2, -2.35, "n=%d, N=%d" % п, ha="center", fontsize=10, fontweight="bold", color=ТЕКСТ)
        ax.text(x0 + 2, -1.75, "эталон: " + " · ".join(str(x) for x in ЭТАЛОН[п]), ha="center", fontsize=7.3, color=СИНИЙ)
        for k, (код, _, цвет) in enumerate(МЕТРИКИ):
            кирпич(ax, x0 + k + 0.2, -1.4, цвет, w=0.6, h=0.6, r=0.17, подпись=код, размер_текста=6.5)
    заголовок(ax, "A. Стена предсказаний: цветной кирпичик — попал в эталон, серый штырёк — мимо (число — ответ модели)", y=1.02)


def график_a_парето(ax):
    итоги = _итоги()
    точки = {м: (ВРЕМЯ_СЕК[м], sum(итоги[м])) for м in ВРЕМЯ_СЕК}
    pf = [(м, t, s) for м, (t, s) in точки.items()
          if not any((t2 <= t and s2 >= s) and (t2 < t or s2 > s) for м2, (t2, s2) in точки.items() if м2 != м)]
    pf.sort(key=lambda x: x[1])
    ax.set_facecolor(ПЛИТА)
    ax.step([p[1] for p in pf], [p[2] for p in pf], where="post", color=ТЕКСТ, linewidth=2.4, zorder=2)
    for м, (t, s) in точки.items():
        на_границе = any(p[0] == м for p in pf)
        цвет = ЖЁЛТЫЙ if на_границе else СЕРЫЙ_КИРПИЧ
        ax.scatter(t, s, s=520, marker="s", color=цвет, edgecolor=_оттенок(цвет, 0.7), linewidth=1.4, zorder=4)
        ax.scatter(t, s, s=150, marker="o", color=_оттенок(цвет, 1.07), edgecolor=_оттенок(цвет, 0.7), linewidth=1.0, zorder=5)
        ax.annotate("%s\n%d с · %d/24" % (м, t, s), (t, s), textcoords="offset points", xytext=(16, 6), fontsize=9, color=ТЕКСТ, fontweight="bold")
    ax.set_xscale("log")
    ax.set_xlim(8, 1500)
    ax.set_ylim(-1.5, 18)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(2))
    ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
    ax.set_xticks([10, 30, 100, 300, 1000])
    ax.grid(color="white", linewidth=1.6, zorder=0)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlabel("время ответа, секунды (log): левее — быстрее ←", color=ТЕКСТ)
    ax.set_ylabel("собрано кирпичиков из 24 ↑", color=ТЕКСТ)
    заголовок(ax, "A. Скорость против точности: граница Парето (быстрее ← и точнее ↑)")
    сноска(ax, "Жёлтые — недоминируемые (никто не быстрее и точнее одновременно). Qwen и Gemini: время не замерено.", y=-0.16)


def график_b_доли(ax):
    """Кирпичик = одна проверка: цвет — прошла, красный — провалена, пустой штырёк — не запускалась."""
    порядок = sorted(B_УЧАСТНИКИ, key=lambda m: (-B_ПРОШЛО[m][0] / B_ПРОШЛО[m][1], m))
    шаг, слотов = 1.35, 18
    _холст(ax, слотов + 6.2, шаг * len(порядок) + 1.0, xmin=-5.8, ymin=-1.7)
    легенда(ax, [(ЖЁЛТЫЙ, "NNL: проверка пройдена"), (СЕРЫЙ_КИРПИЧ, "чат: пройдена"), (КРАСНЫЙ, "провалена"),
                 (None, "не запускалась")], -5.6, -1.5)
    # чаты в тесте провалили проверку «категория после врача»: в строке красный кирпичик стоит последним среди запущенных
    for ряд, м in enumerate(порядок):
        y = ряд * шаг
        прошло, всего = B_ПРОШЛО[м]
        плита(ax, -0.15, y - 0.12, слотов + 0.3, 1.24)
        ax.text(-0.5, y + 0.5, м, ha="right", va="center", fontsize=10.5, fontweight="bold", color=ТЕКСТ)
        цвет_ok = ЖЁЛТЫЙ if м == NNL else СЕРЫЙ_КИРПИЧ
        for k in range(слотов):
            if k < прошло:
                кирпич(ax, k, y, цвет_ok)
            elif k < всего:
                кирпич(ax, k, y, КРАСНЫЙ)
            else:
                штырёк_пустой(ax, k, y)
        ax.text(слотов + 0.45, y + 0.5, "%d/%d · %.0f%%" % (прошло, всего, 100 * прошло / всего), va="center", fontsize=10.5,
                fontweight="bold", color=ТЕКСТ)
    заголовок(ax, "B. Ваш бенч «система»: сколько проверок пройдено (Higher is better ↑)")
    сноска(ax, "Проверки из кода бенча NNL. NNL — 4 сценария (18 проверок), чаты — 3 сценария (15). Веб-поиск у чатов включён по умолчанию.", y=-0.04)


def график_b_матрица(ax):
    проверки = list(B_ПРОВЕРКИ)
    ширина, высота, шаг_х, шаг_y = 2.0, 1.0, 2.2, 1.25
    _холст(ax, шаг_х * len(проверки) + 0.3, шаг_y * len(B_УЧАСТНИКИ) + 0.2, xmin=-5.4, ymin=-2.2)
    for c, п in enumerate(проверки):
        ax.text(c * шаг_х + ширина / 2, -0.55, п, ha="center", va="bottom", fontsize=8.2, color=ТЕКСТ, fontweight="bold")
    for r, м in enumerate(B_УЧАСТНИКИ):
        y = r * шаг_y
        ax.text(-0.35, y + высота / 2, м, ha="right", va="center", fontsize=10.5, fontweight="bold", color=ТЕКСТ)
        for c, п in enumerate(проверки):
            a, b = B_ПРОВЕРКИ[п][м]
            цвет = ЗЕЛЁНЫЙ if a == b else (КРАСНЫЙ if a == 0 else ЖЁЛТЫЙ)
            x = c * шаг_х
            кирпич(ax, x, y, цвет, w=ширина, h=высота, r=0.2, штырьки=2)
            ax.text(x + ширина / 2, y + высота / 2, "%d/%d" % (a, b), ha="center", va="center", fontsize=9.5, fontweight="bold",
                    color=ТЕКСТ if цвет == ЖЁЛТЫЙ else "white", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.18", fc=_оттенок(цвет, 0.9), ec="none", alpha=0.95))
    заголовок(ax, "B. Где именно ломаются: проверка × участник (зелёный — все, жёлтый — часть, красный — ни одной)", y=1.0)


def сохранить(fig, имя, dpi=230):
    путь = os.path.join(ПАПКА, имя)
    fig.savefig(путь, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("записано:", путь)
    return путь


def сводка(пути):
    """Сводка: те же картинки одной страницей."""
    import matplotlib.image as mpimg
    f = plt.figure(figsize=(17, 13))
    f.suptitle("NNL · канон бенчмарка в духе Lego · прогон 13.10.2026 · одна попытка на сценарий", fontsize=15, fontweight="bold", y=0.995, color=ТЕКСТ)
    сетка = f.add_gridspec(3, 2, height_ratios=[1, 1, 1.05], hspace=0.06, wspace=0.03)
    места = [(0, 0), (0, 1), (1, 0), (1, 1), (2, slice(0, 2))]
    for (рядок, колонка), путь in zip(места, пути):
        a = f.add_subplot(сетка[рядок, колонка])
        a.imshow(mpimg.imread(путь))
        a.axis("off")
    сохранить(f, "0_сводка.png", dpi=240)


def main():
    пути = []
    f, ax = plt.subplots(figsize=(11.5, 4.6)); график_a_баллы(ax); пути.append(сохранить(f, "1_A_баллы.png"))
    f, ax = plt.subplots(figsize=(17, 5.2)); график_a_тепловая(ax); пути.append(сохранить(f, "2_A_стена.png"))
    f, ax = plt.subplots(figsize=(8.8, 5.4)); график_a_парето(ax); пути.append(сохранить(f, "3_A_парето.png"))
    f, ax = plt.subplots(figsize=(11.5, 5.2)); график_b_доли(ax); пути.append(сохранить(f, "4_B_проверки.png"))
    f, ax = plt.subplots(figsize=(12, 5.8)); график_b_матрица(ax); пути.append(сохранить(f, "5_B_матрица.png"))
    сводка([пути[0], пути[2], пути[3], пути[4], пути[1]])
    json.dump({"эталон": {"%d,%d" % k: v for k, v in ЭТАЛОН.items()},
               "предсказания": {m: {"%d,%d" % k: v for k, v in d.items()} for m, d in ПРЕДСКАЗАНИЯ.items()},
               "итоги_A": _итоги(), "B_прошло": B_ПРОШЛО, "время_A_сек": ВРЕМЯ_СЕК},
              open(os.path.join(ПАПКА, "данные.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
