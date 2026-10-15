# -*- coding: utf-8 -*-
"""Идеал NNL одной картинкой: общий стол (шина), блоки-кирпичики, шеф без рецептов, два захода, сборка с честным «не знаю».
Сплошная рамка — уже есть в коде, пунктир — цель. Запуск: python NNL/диалог/схемы/схема_идеал.py → схема_идеал.png и .svg."""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ПАПКА = os.path.dirname(os.path.abspath(__file__))
UNIT, DPI = 0.07, 150
plt.rcParams["font.family"] = "Segoe UI"
plt.rcParams["svg.fonttype"] = "path"
W, H = 306, 178
ТЕКСТ = "#1A1A1A"
FS_З, FS_Т, FS_М = 12.8, 11.0, 10.4
ЦВ = {"блок": ("#E7E3F9", "#4A3FA6"), "шеф": ("#DCEAF9", "#1D5CA6"), "ии": ("#FCE6DA", "#A8431D"), "стол": ("#FFF0CC", "#8A5F00"),
      "защита": ("#DDF2E7", "#1B7A4B"), "нейтр": ("#F1F1F1", "#3A3A3A")}
ПРЕДУПРЕЖДЕНИЯ = []

_fig = plt.figure(figsize=(4, 4), dpi=DPI)
_rend = _fig.canvas.get_renderer()


def ширина(s, fs, bold=False):
    t = _fig.text(0, 0, s, fontsize=fs, fontweight="bold" if bold else "normal")
    w = t.get_window_extent(_rend).width / DPI / UNIT
    t.remove()
    return w


def перенос(s, fs, макс, bold=False):
    out = []
    for абзац in s.split("\n"):
        тек = ""
        for слово in абзац.split():
            проба = (тек + " " + слово).strip()
            if ширина(проба, fs, bold) <= макс or not тек:
                тек = проба
            else:
                out.append(тек)
                тек = слово
        out.append(тек)
    return out


def лш(fs):
    return fs * 1.28 / 72 / UNIT


def плашка(ax, x, y, w, h, fc, ec, lw=1.3, ls="-", r=2.0, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))


def карточка(ax, x, y, w, h, заг, под, ключ, цель=False, залить=True, жирно=False):
    фон, ак = ЦВ[ключ]
    плашка(ax, x, y, w, h, фон if залить else "white", ак, lw=1.9 if жирно else 1.3, ls=(0, (4, 2.5)) if цель else "-", z=3)
    строки_з = перенос(заг, FS_З - 0.4, w - 5, True)
    строки_п = перенос(под, FS_М, w - 5) if под else []
    нужно = 2.2 + len(строки_з) * лш(FS_З - 0.4) + len(строки_п) * лш(FS_М) + 1.2
    if нужно > h + 0.3:
        ПРЕДУПРЕЖДЕНИЯ.append("не помещается: %s (нужно %.1f, есть %.1f)" % (заг, нужно, h))
    yy = y + 2.2
    for s in строки_з:
        ax.text(x + 2.6, yy + лш(FS_З - 0.4) / 2, s, fontsize=FS_З - 0.4, fontweight="bold", color=ак, va="center", zorder=5)
        yy += лш(FS_З - 0.4)
    for s in строки_п:
        ax.text(x + 2.6, yy + лш(FS_М) / 2 + 0.2, s, fontsize=FS_М, color="#2A2A2A", va="center", zorder=5)
        yy += лш(FS_М)


def кирпич(ax, x, y, w, h, заг, под, цель=False, studs=3):
    """Блок как деталь Lego: корпус и шпеньки сверху."""
    фон, ак = ЦВ["блок"]
    ls = (0, (4, 2.5)) if цель else "-"
    sw = 5.0
    gap = (w - studs * sw) / (studs + 1)
    for i in range(studs):
        plashka_x = x + gap + i * (sw + gap)
        плашка(ax, plashka_x, y - 3.2, sw, 3.6, фон, ак, lw=1.2, ls=ls, r=1.0, z=2)
    плашка(ax, x, y, w, h, фон, ак, lw=1.5, ls=ls, r=2.0, z=3)
    ax.text(x + 2.6, y + 2.2 + лш(FS_З - 0.4) / 2, заг, fontsize=FS_З - 0.4, fontweight="bold", color=ак, va="center", zorder=5)
    yy = y + 2.2 + лш(FS_З - 0.4)
    for s in перенос(под, FS_М, w - 5):
        ax.text(x + 2.6, yy + лш(FS_М) / 2 + 0.2, s, fontsize=FS_М, color="#2A2A2A", va="center", zorder=5)
        yy += лш(FS_М)
    if yy + 1 > y + h + 0.3:
        ПРЕДУПРЕЖДЕНИЯ.append("кирпич не помещается: " + заг)


def стрелка(ax, p1, p2, цвет="#555555", ls="-", две=False, lw=1.5):
    ax.annotate("", xy=p2, xytext=p1, arrowprops=dict(arrowstyle="<|-|>" if две else "-|>", color=цвет, lw=lw, shrinkA=0, shrinkB=0, mutation_scale=12, ls=ls), zorder=4)


def рисовать():
    fig = plt.figure(figsize=(W * UNIT, H * UNIT), dpi=DPI, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")

    ax.text(8, 9, "NNL: куда мы идём", fontsize=21, fontweight="bold", color=ТЕКСТ, va="center")
    ax.text(8, 17, "Кухня с общим столом: блоки-поваров можно докручивать друг к другу, шеф не знает рецептов, а ИИ только слушает и говорит.", fontsize=11.4, color="#555555", va="center")
    плашка(ax, 200, 5.4, 12, 6, "white", "#3A3A3A", lw=1.3, r=1.4)
    ax.text(215, 8.4, "уже есть", fontsize=10.4, va="center")
    плашка(ax, 240, 5.4, 12, 6, "white", "#3A3A3A", lw=1.3, ls=(0, (4, 2.5)), r=1.4)
    ax.text(255, 8.4, "цель", fontsize=10.4, va="center")

    YB, HB = 36, 27            # кирпичи
    YF, HF = 66, 8.4           # предохранители
    YS, HS = 80, 27            # общий стол
    YR, HR = 115, 21           # шеф, сборка, рассказчик
    YN, HN = 144, 15           # нижний ряд

    # ---------- человек и слушатель
    карточка(ax, 8, 54, 52, 14, "Человек", "говорит как умеет", "нейтр")
    карточка(ax, 8, 80, 52, 27, "ИИ-слушатель", "реплика → факты на общем языке. Видит только реплику, документов не видит", "ии")
    стрелка(ax, (34, 68), (34, 80))
    стрелка(ax, (60, YS + HS / 2), (68, YS + HS / 2))

    # ---------- кирпичи
    X = [68, 112, 156]
    кирпич(ax, X[0], YB, 38, HB, "Блок A", "паспорт: пишет, читает, ответы. Свои веса", False)
    кирпич(ax, X[1], YB, 38, HB, "Блок B", "учится отдельно, старые заморожены", False)
    фон, ак = ЦВ["блок"]
    for i in range(3):
        плашка(ax, X[2] + 4 + i * 11, YB - 3.2, 5, 3.6, фон, ак, lw=1.2, ls=(0, (4, 2.5)), r=1.0, z=2)
    плашка(ax, X[2], YB, 38, HB, фон, ак, lw=1.5, ls=(0, (4, 2.5)), z=3)
    ax.text(X[2] + 2.6, YB + 2.2 + лш(FS_З - 0.4) / 2, "Составной блок", fontsize=FS_З - 0.4, fontweight="bold", color=ак, va="center", zorder=5)
    for i in range(3):
        плашка(ax, X[2] + 2.6 + i * 11.4, YB + 8.6, 10.2, 6.4, "white", ак, lw=1.0, r=1.2, z=4)
        ax.text(X[2] + 2.6 + i * 11.4 + 5.1, YB + 11.9, "блок", fontsize=8.0, color=ак, ha="center", va="center", zorder=6)
    for s_i, s_ in enumerate(перенос("докручены друг к другу: снаружи один блок", FS_М, 33)):
        ax.text(X[2] + 2.6, YB + 18.4 + s_i * лш(FS_М), s_, fontsize=FS_М, color="#2A2A2A", va="center", zorder=5)
    плашка(ax, 200, YB, 34, HB, "white", ак, lw=1.3, ls=(0, (4, 2.5)), z=3)
    ax.text(217, YB + 7.5, "+", fontsize=24, color=ак, ha="center", va="center", zorder=5)
    for s_i, s_ in enumerate(перенос("новый блок рядом, остальные не трогаются", FS_М, 30)):
        ax.text(217, YB + 16.2 + s_i * лш(FS_М), s_, fontsize=FS_М, color="#2A2A2A", ha="center", va="center", zorder=5)

    # ---------- предохранители
    for x in [X[0], X[1], X[2], 200]:
        плашка(ax, x + 4, YF, 26, HF, "white", ЦВ["защита"][1], lw=1.2, ls=(0, (4, 2.5)), r=1.4, z=3)
        ax.text(x + 17, YF + HF / 2, "калибровка · предел", fontsize=8.2, color=ЦВ["защита"][1], ha="center", va="center", zorder=5, fontweight="bold")
        стрелка(ax, (x + 12, YB + HB), (x + 12, YF))
        стрелка(ax, (x + 12, YF + HF), (x + 12, YS))
        стрелка(ax, (x + 24, YS), (x + 24, YF + HF), ls=(0, (3, 2)))
        стрелка(ax, (x + 24, YF), (x + 24, YB + HB), ls=(0, (3, 2)))

    # ---------- общий стол
    ф, а = ЦВ["стол"]
    плашка(ax, 68, YS, 170, HS, ф, а, lw=1.9, z=2)
    ax.text(72, YS + 5.6, "Общий стол (шина)", fontsize=FS_З + 0.6, fontweight="bold", color=а, va="center", zorder=5)
    ax.text(72, YS + 12.2, "понятие → число. Блоки читают и пишут только здесь, напрямую друг с другом не говорят", fontsize=FS_М, color="#2A2A2A", va="center", zorder=5)
    for i, т in enumerate(["область: 0,8", "понятие: −1,2", "понятие: 2,5", "понятие: 0,1", "…"]):
        плашка(ax, 72 + i * 32.6, YS + 17.2, 29.4, 6.6, "white", а, lw=1.0, r=1.2, z=4)
        ax.text(72 + i * 32.6 + 14.7, YS + 20.5, т, fontsize=8.6, color=а, ha="center", va="center", zorder=6)
    ax.text(242, YF + 3, "заход 1: каждый блок\nотвечает сам, стол пуст", fontsize=FS_М, color="#444444", va="center", zorder=5, linespacing=1.15)
    ax.text(242, YS + 12, "заход 2: только при споре,\nблоки видят ответы и\nуверенность соседей", fontsize=FS_М, color="#444444", va="center", zorder=5, linespacing=1.15)

    # ---------- шеф, сборка, рассказчик
    карточка(ax, 68, YR, 76, HR, "Шеф (ядро)", "без обученных чисел и рецептов предметной области. Решает по техкарте: кого звать, нужен ли заход 2", "шеф", жирно=True)
    карточка(ax, 150, YR, 88, HR, "Сборка и «не знаю»", "ответ по честной уверенности блоков или отказ с причиной: кто спорил", "шеф")
    стрелка(ax, (106, YS + HS), (106, YR))
    стрелка(ax, (144, YR + HR / 2), (150, YR + HR / 2), две=True)
    карточка(ax, 246, YR, 52, HR, "ИИ-рассказчик", "досье → текст. Ничего не ищет и не решает", "ии")
    стрелка(ax, (238, YR + HR / 2), (246, YR + HR / 2))
    карточка(ax, 246, YN, 52, HN, "Ответ", "человеку", "нейтр")
    стрелка(ax, (272, YR + HR), (272, YN))
    карточка(ax, 8, YR, 52, HR, "Заготовки", "вопросы и таблицы готовятся заранее: ход без вызова модели", "защита")
    стрелка(ax, (60, YR + HR / 2), (68, YR + HR / 2), цвет=ЦВ["защита"][1], ls=(0, (3, 2)))

    # ---------- нижний ряд
    плашка(ax, 8, YN, 52, HN, "white", ЦВ["блок"][1], lw=1.2, ls=(0, (4, 2.5)), z=3)
    ax.text(34, YN + 5, "блок вынут", fontsize=FS_Т, color=ЦВ["блок"][1], ha="center", va="center", zorder=5, fontweight="bold")
    ax.text(34, YN + 10.4, "и возвращён: всё как было", fontsize=FS_М, color="#2A2A2A", ha="center", va="center", zorder=5)
    карточка(ax, 68, YN, 76, HN, "Техкарта = файл", "новое блюдо — новый файл: участники, заходы, пороги, сборка, отказ", "нейтр")
    карточка(ax, 150, YN, 88, HN, "Больничный", "блок вынут: его знание ушло, остальные работают, потеря измерена", "защита")

    ax.plot([8, W - 8], [YN + HN + 5, YN + HN + 5], color="#C8C8C8", lw=0.8)
    ax.text(8, YN + HN + 9, "Скорость, качество, экономия: модель вызывается только у слушателя и рассказчика, всё остальное считается быстро и без токенов.", fontsize=FS_М, color="#444444", va="center")

    for расш in ("png", "svg"):
        путь = os.path.join(ПАПКА, "схема_идеал." + расш)
        fig.savefig(путь, dpi=DPI, facecolor="white")
        print("записано:", путь)
    for п in ПРЕДУПРЕЖДЕНИЯ:
        print("ВНИМАНИЕ:", п)


if __name__ == "__main__":
    рисовать()
