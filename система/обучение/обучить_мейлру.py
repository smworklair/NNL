# -*- coding: utf-8 -*-
"""Обучение блока «ответы_мейлру»: ТОЛЬКО стиль живого общения + понимание типа вопроса.

Содержание про военкомат/призыв НЕ учим: оно живет в блоках «здоровье»/«право».
Блок видит только текст вопроса (такт 1, пустая шина), веса чтения шины V=0.

Две задачи (обе без привязки к теме):
  1. Тип вопроса (8 классов) — слабая разметка правилами по тексту вопроса.
  2. Стиль ответа (6 классов) — правила по ЛУЧШЕМУ ответу (длина/тон/совет/
     обращение/вопрос в ответ), предсказывается по тексту вопроса
     (как сообщество ОТВЕТИЛО БЫ на такой тип вопроса).

Тематические слова перед обучением маскируются (заменяются пробелом).
Деление train/dev/test — по qid (md5), без утечки одинаковых вопросов.
Обучение: CPU, numpy, хэшированные признаки (как у «здоровья»),
Адам вручную, совместный лосс двух голов с общей матрицей E.

Ответы блока (14): 8 вопросных + 6 стилевых, все с префиксом
«ответ:мейлру:» для совместимости. Одна матрица U (d,14): первые 8 столбцов —
голова вопроса, следующие 6 — голова стиля. Два отдельных softmax при обучении.
На инференсе проход2 возвращает все 14 счетов; для метрик берем argmax
внутри каждой головы. Глобальный margin (top1-top2 по всем 14) — оценка
уверенности для решателя с порогом.

Читает: только собственное понятие «вывод_ответы_мейлру» (не тематическое),
V нулевая — такт 2 счетов не меняет, но дает синтез живого текста,
когда блок уверен. Пишет: «вывод_ответы_мейлру», «стиль:живой_ответ»
(соседи их не читают — вставка 0 изменений).

Запуск: python -X utf8 v8/обучение/обучить_мейлру.py [--зерно 42] [--быстро]
"""
import datetime
import hashlib
import json
import os
import re
import sys
import zlib

import numpy as np

sys.dont_write_bytecode = True
ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
V8 = os.path.dirname(ЗДЕСЬ)
КОРЕНЬ = os.path.dirname(V8)
sys.path.insert(0, V8)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ядро import Язык  # noqa: E402

ЗЕРНО_ПО_УМОЛЧАНИЮ = 42
ЯЗЫК = Язык(os.path.join(V8, "язык"))
ПАПКА_БЛОКА = os.path.join(V8, "блоки", "основная_внешние.з1", "ответы_мейлру")
ДАННЫЕ = os.path.join(КОРЕНЬ, "данные", "otvetmailru", "куски")
ГОТОВО = os.path.join(КОРЕНЬ, "данные", "otvetmailru", "готово")

# Используем первые 6 кусков (aa-af): ~15 млн прочитанных записей, ~600 тыс. отобранных.
# Этого достаточно для CPU-обучения; полный скан 129 млн записей не нужен.
ЧАНКИ = ["aa", "ab", "ac", "ad", "ae", "af"]

B = 16384
D = 32
СОЛЬ = "ответы_мейлру"
МАСШТАБ = 8.0

# ---------------------------------------------------------------- классы
# Вопрос: 8 классов, приоритет сверху вниз (первое совпадение побеждает).
# Правила — по форме/намерению, НЕ по теме.
ВОПРОС_КЛАССЫ = [
    "что_делать",
    "можно_ли",
    "как_оформить",
    "боюсь",
    "правда_ли",
    "куда_обратиться",
    "уточнение",
    "поделиться",
]
ВП = {
    "боюсь": re.compile(r"боюсь|страшно|переживаю|волнуюсь|паник|тревож|боязно|страх|не хочу.*служ|не хочу.*арм", re.I),
    "правда_ли": re.compile(r"правда ли|говорят что|слышал что|действительно ли|это правда|разве|неужели|ходят слухи|говорят,?\s*что", re.I),
    "куда_обратиться": re.compile(r"куда\s+(идти|обратиться|писать|звонить|жаловаться)|к кому|подскажите куда|кто может.*проконсульт|куда жаловаться|куда писать|куда обратит|к кому обратит", re.I),
    "как_оформить": re.compile(r"как оформить|какие документы|какие нужны|порядок оформ|как получить|образец|заявлен|как написать|какие справки|что нужно.*документ|как заполнит|перечень документов", re.I),
    "можно_ли": re.compile(r"можно ли|законно ли|имеет?\s*(ли\s+)?право|положено ли|могут ли|обязан|заберут|возьмут|призовут|годен ли|дадут ли|освободят|возможно ли|является ли|входит ли|могу ли|может ли", re.I),
    "что_делать": re.compile(r"что делать|как быть|как поступить|помогите|что мне делать|что посоветуете|подскажите|посоветуйте|^как\b|че делать|чё делать|что делать\??$", re.I),
    "уточнение": re.compile(r"а если|а у меня|а в мо[её]м|сколько|когда|где именно|какой срок|через сколько|что означает|что значит|что будет|почему|зачем|какая статья|какой штраф|какая категор|сколько служ|как долго|\s+ли\s+|\?|или нет", re.I),
}
# Порядок применения (специфичные раньше общих; уточнение-вопросы раньше fallback):
ПОРЯДОК_В = ["боюсь", "правда_ли", "куда_обратиться", "как_оформить", "можно_ли", "что_делать", "уточнение"]

# Стиль: 6 классов по ЛУЧШЕМУ ответу. Приоритет сверху вниз.
СТИЛЬ_КЛАССЫ = [
    "вопрос_в_ответ",
    "ссылка_на_норму",
    "личный_опыт",
    "эмоциональный",
    "короткий_прямой",
    "подробный_деловой",
]
СП_ВОПРОС = re.compile(r"\?")
СП_НОРМА = re.compile(r"закон|статья|фз|кодекс|пункт|положени|постановление|ук рф|коап|кас\b", re.I)
СП_ОПЫТ = re.compile(r"\bя\b|\bмне\b|у меня|мой\b|служил|часть|сталкивался|мой сын|мой брат", re.I)
СП_ЭМО = re.compile(r"\)\)|хаха|аха|лол|ржу|прикол|:\)|:-\(|;\)|не переживай|не волнуй|успокой|держись|понимаю|сочувств|соболезн|крепись|вс[её] будет|не бойся|привет|здравствуй|дорогой|родной|друг\b|брат\b|красав", re.I)
ПОРОГ_ДЛИНЫ = 150  # остаток: <150 короткий_прямой, >=150 подробный_деловой


def разметить_вопрос(текст):
    t = текст or ""
    for имя in ПОРЯДОК_В:
        if ВП[имя].search(t):
            return имя
    return "поделиться"


def разметить_стиль(лучший, ответы=None):
    """Стиль лучшего ответа. Если лучшего нет — берем первый длинный ответ."""
    b = (лучший or "").strip()
    if not b and ответы:
        for a in (ответы or []):
            t = (a.get("t") or "")
            if len(t) >= 20:
                b = t
                break
    if not b:
        return None
    if СП_ВОПРОС.search(b):
        return "вопрос_в_ответ"
    if СП_НОРМА.search(b):
        return "ссылка_на_норму"
    if СП_ОПЫТ.search(b):
        return "личный_опыт"
    if СП_ЭМО.search(b):
        return "эмоциональный"
    if len(b) >= ПОРОГ_ДЛИНЫ:
        return "подробный_деловой"
    return "короткий_прямой"


# Тематические слова: маскируются перед обучением (замена пробелом).
# Список из фильтр.py (ключи призыва) + частые медицинские/правовые термины
# (названия болезней и статей — грубым списком основ, без привязки к смыслу).
ТЕМАТИКА = re.compile(
    r"военкомат|призыв|призов|в\s+арми|армию|армии|армейск|повестк|отсрочк|"
    r"военн\w*\s*билет|военник|приписн|медкомисси|срочн\w*\s*служ|годност|"
    r"ввк\b|откос|закос|воинск|служб\w*|контракт|дедовщин|"
    r"плоскостоп|сколиоз|астм|гипертони|гастрит|язв|гепатит|туберкул|вич\b|"
    r"диабет|эпилепс|близорукост|зрени|слух\b|сердц|давлени|позвоночник|"
    r"колен|сустав|грыж|остеохондроз|псих\w*|невроз|депресси|аллерги|"
    r"стать\w*\s*\d+|расписани|болезн|диагноз|категори\w*\s*[абвгд]|"
    r"фз\b|53-?фз|565|663|кас\b|коап|ук\s*рф|повестк",
    re.I,
)


def маскировать(текст):
    return ТЕМАТИКА.sub(" ", текст or "")


# Простая базовая линия «по ключевым словам» (намеренно бедная: 1-2 ключа/класс).
БАЗА_КЛЮЧИ_В = {
    "что_делать": re.compile(r"что делать", re.I),
    "можно_ли": re.compile(r"можно ли", re.I),
    "как_оформить": re.compile(r"как оформить", re.I),
    "боюсь": re.compile(r"боюсь", re.I),
    "правда_ли": re.compile(r"правда", re.I),
    "куда_обратиться": re.compile(r"куда", re.I),
    "уточнение": re.compile(r"сколько", re.I),
}
БАЗА_ПОРЯДОК_В = ["что_делать", "можно_ли", "как_оформить", "боюсь", "правда_ли", "куда_обратиться", "уточнение"]


def база_ключевые_вопрос(текст):
    for имя in БАЗА_ПОРЯДОК_В:
        if БАЗА_КЛЮЧИ_В[имя].search(текст or ""):
            return имя
    return "поделиться"


def база_ключевой_стиль(текст):
    t = (текст or "").lower()
    if "боюсь" in t or "страшно" in t:
        return "эмоциональный"
    if "можно ли" in t:
        return "ссылка_на_норму"
    if "подскажите" in t or "помогите" in t or "что делать" in t:
        return "подробный_деловой"
    if "?" in t:
        return "вопрос_в_ответ"
    return "короткий_прямой"


# ---------------------------------------------------------------- данные
def qid_доля(qid):
    h = hashlib.md5((qid or "").encode("utf-8")).hexdigest()
    return (int(h[:8], 16) % 1000) / 1000.0


def загрузить_строки(лимит_кат=None):
    """Читает выбранные чанки, возвращает список сырых записей + статистику скана."""
    сырые = []
    просканировано = 0
    отобрано_файлов = 0
    счет_кат = {}
    for ч in ЧАНКИ:
        try:
            гот = json.load(open(os.path.join(ГОТОВО, ч), encoding="utf-8"))
            просканировано += гот.get("записей", 0)
        except OSError:
            pass
        папка = os.path.join(ДАННЫЕ, ч)
        for имя in ("армия", "ключи", "право", "болезни", "фон"):
            путь = os.path.join(папка, имя + ".jsonl")
            if not os.path.exists(путь):
                continue
            with open(путь, encoding="utf-8") as f:
                for строка in f:
                    строка = строка.strip()
                    if not строка:
                        continue
                    try:
                        r = json.loads(строка)
                    except ValueError:
                        continue
                    отобрано_файлов += 1
                    счет_кат[имя] = счет_кат.get(имя, 0) + 1
                    if лимит_кат and счет_кат[имя] > лимит_кат.get(имя, 10 ** 9):
                        continue
                    вопрос = r.get("вопрос") or ""
                    пояснение = r.get("пояснение") or ""
                    if not вопрос and not пояснение:
                        continue
                    сырые.append({
                        "qid": r.get("qid") or "",
                        "кат": r.get("кат") or имя,
                        "файл_кат": имя,
                        "текст": (вопрос + " " + пояснение).strip(),
                        "лучший": r.get("лучший") or "",
                        "ответы": r.get("ответы") or [],
                    })
    return сырые, просканировано, отобрано_файлов, счет_кат


def индекс(токен):
    return zlib.crc32((СОЛЬ + "\x1f" + токен).encode("utf-8")) % B


def токены_текста(текст):
    return ЯЗЫК.перевести(текст)["токены"]


# ---------------------------------------------------------------- обучение
def softmax(s):
    m = s.max(axis=1, keepdims=True)
    e = np.exp(s - m)
    return e / e.sum(axis=1, keepdims=True)


def обучить_матрицу(X_idx, X_ptr, yq, ys, Yq, Ys, seed, эпох=12, пакет=256, lr=0.05, лямбда=1e-5):
    """Совместное обучение одной матрицы E двум головам (вопрос + стиль).
    Стиль учится только на примерах с лучшим ответом (ys>=0)."""
    rng = np.random.RandomState(seed)
    E = (rng.randn(B, D) * 0.05).astype(np.float64)
    Uq = (rng.randn(D, Yq) * 0.05).astype(np.float64)
    bq = np.zeros(Yq, np.float64)
    # --- стадия 1: вопрос (E + Uq) ---
    mE = np.zeros_like(E)
    vE = np.zeros_like(E)
    mUq = np.zeros_like(Uq)
    vUq = np.zeros_like(Uq)
    mbq = np.zeros_like(bq)
    vbq = np.zeros_like(bq)
    b1, b2, eps = 0.9, 0.999, 1e-8
    t = 0
    n = len(yq)
    for ep in range(эпох):
        perm = rng.permutation(n)
        for s0 in range(0, n, пакет):
            t += 1
            idx = perm[s0:s0 + пакет]
            m = len(idx)
            h = np.zeros((m, D))
            lens = np.zeros(m)
            for j, r in enumerate(idx):
                a, b_ = X_ptr[r], X_ptr[r + 1]
                ii = X_idx[a:b_]
                lens[j] = max(1, len(ii))
                if len(ii):
                    h[j] = E[ii].sum(0)
            h = h / np.sqrt(lens)[:, None]
            sq = h @ Uq + bq
            pq = softmax(sq)
            dsq = pq
            for j, r in enumerate(idx):
                dsq[j, yq[r]] -= 1.0
            dsq /= m
            gUq = h.T @ dsq + лямбда * Uq
            gbq = dsq.sum(0)
            dh = dsq @ Uq.T
            for (g, mp, vp, P) in ((gUq, mUq, vUq, Uq),
                                  (gbq[None, :], mbq[None, :], vbq[None, :], bq[None, :])):
                mp[:] = b1 * mp + (1 - b1) * g
                vp[:] = b2 * vp + (1 - b2) * g * g
                P[:] -= lr * (mp / (1 - b1 ** t)) / (np.sqrt(vp / (1 - b2 ** t)) + eps)
            dh_n = dh / np.sqrt(lens)[:, None]
            все = np.concatenate([X_idx[X_ptr[r]:X_ptr[r + 1]] for r in idx]) if m else np.zeros(0, int)
            if len(все):
                повт = np.concatenate([np.repeat(dh_n[j:j + 1], X_ptr[r + 1] - X_ptr[r], axis=0)
                                       for j, r in enumerate(idx)])
                uniq, inv = np.unique(все, return_inverse=True)
                gE = np.zeros((len(uniq), D))
                np.add.at(gE, inv, повт)
                gE += лямбда * E[uniq]
                mE[uniq] = b1 * mE[uniq] + (1 - b1) * gE
                vE[uniq] = b2 * vE[uniq] + (1 - b2) * gE * gE
                E[uniq] -= lr * (mE[uniq] / (1 - b1 ** t)) / (np.sqrt(vE[uniq] / (1 - b2 ** t)) + eps)
    # --- стадия 2: стиль (зонд на замороженной E, сильная регуляризация) ---
    Us = (rng.randn(D, Ys) * 0.01).astype(np.float64)
    bs = np.zeros(Ys, np.float64)
    mUs = np.zeros_like(Us)
    vUs = np.zeros_like(Us)
    mbs = np.zeros_like(bs)
    vbs = np.zeros_like(bs)
    idx_s = np.flatnonzero(ys >= 0)
    ns = len(idx_s)
    t = 0
    lam_s = 1e-3
    for ep in range(30):
        perm = idx_s[rng.permutation(ns)]
        for s0 in range(0, ns, пакет):
            t += 1
            idx = perm[s0:s0 + пакет]
            m = len(idx)
            h = np.zeros((m, D))
            lens = np.zeros(m)
            for j, r in enumerate(idx):
                a, b_ = X_ptr[r], X_ptr[r + 1]
                ii = X_idx[a:b_]
                lens[j] = max(1, len(ii))
                if len(ii):
                    h[j] = E[ii].sum(0)
            h = h / np.sqrt(lens)[:, None]
            ss = h @ Us + bs
            ps = softmax(ss)
            dss = ps
            for j, r in enumerate(idx):
                dss[j, ys[r]] -= 1.0
            dss /= m
            gUs = h.T @ dss + lam_s * Us
            gbs = dss.sum(0)
            for (g, mp, vp, P) in ((gUs, mUs, vUs, Us),
                                  (gbs[None, :], mbs[None, :], vbs[None, :], bs[None, :])):
                mp[:] = b1 * mp + (1 - b1) * g
                vp[:] = b2 * vp + (1 - b2) * g * g
                P[:] -= (lr * 0.5) * (mp / (1 - b1 ** t)) / (np.sqrt(vp / (1 - b2 ** t)) + eps)
    U = np.concatenate([Uq, Us], axis=1)
    b = np.concatenate([bq, bs])
    return E.astype(np.float32), U.astype(np.float32), b.astype(np.float32)


def обучить_совместно(X_idx, X_ptr, yq, ys, Yq, Ys, seed, эпох=12, пакет=256, lr=0.05, лямбда=1e-5):
    """Совместное обучение E двум головам (вопрос + стиль), стиль только где ys>=0."""
    rng = np.random.RandomState(seed)
    E = (rng.randn(B, D) * 0.05).astype(np.float64)
    Uq = (rng.randn(D, Yq) * 0.05).astype(np.float64)
    Us = (rng.randn(D, Ys) * 0.05).astype(np.float64)
    bq = np.zeros(Yq, np.float64)
    bs = np.zeros(Ys, np.float64)
    mE = np.zeros_like(E)
    vE = np.zeros_like(E)
    mUq = np.zeros_like(Uq)
    vUq = np.zeros_like(Uq)
    mUs = np.zeros_like(Us)
    vUs = np.zeros_like(Us)
    mbq = np.zeros_like(bq)
    vbq = np.zeros_like(bq)
    mbs = np.zeros_like(bs)
    vbs = np.zeros_like(bs)
    b1, b2, eps = 0.9, 0.999, 1e-8
    t = 0
    n = len(yq)
    for ep in range(эпох):
        perm = rng.permutation(n)
        for s0 in range(0, n, пакет):
            t += 1
            idx = perm[s0:s0 + пакет]
            m = len(idx)
            h = np.zeros((m, D))
            lens = np.zeros(m)
            for j, r in enumerate(idx):
                a, b_ = X_ptr[r], X_ptr[r + 1]
                ii = X_idx[a:b_]
                lens[j] = max(1, len(ii))
                if len(ii):
                    h[j] = E[ii].sum(0)
            h = h / np.sqrt(lens)[:, None]
            sq = h @ Uq + bq
            ss = h @ Us + bs
            pq = softmax(sq)
            ps = softmax(ss)
            dsq = pq
            dss = ps
            for j, r in enumerate(idx):
                dsq[j, yq[r]] -= 1.0
                if ys[r] >= 0:
                    dss[j, ys[r]] -= 1.0
                else:
                    dss[j, :] = 0.0
            dsq /= m
            dss /= m
            gUq = h.T @ dsq + лямбда * Uq
            gUs = h.T @ dss + лямбда * Us
            gbq = dsq.sum(0)
            gbs = dss.sum(0)
            dh = dsq @ Uq.T + dss @ Us.T
            for (g, mp, vp, P) in ((gUq, mUq, vUq, Uq), (gUs, mUs, vUs, Us),
                                  (gbq[None, :], mbq[None, :], vbq[None, :], bq[None, :]),
                                  (gbs[None, :], mbs[None, :], vbs[None, :], bs[None, :])):
                mp[:] = b1 * mp + (1 - b1) * g
                vp[:] = b2 * vp + (1 - b2) * g * g
                P[:] -= lr * (mp / (1 - b1 ** t)) / (np.sqrt(vp / (1 - b2 ** t)) + eps)
            dh_n = dh / np.sqrt(lens)[:, None]
            все = np.concatenate([X_idx[X_ptr[r]:X_ptr[r + 1]] for r in idx]) if m else np.zeros(0, int)
            if len(все):
                повт = np.concatenate([np.repeat(dh_n[j:j + 1], X_ptr[r + 1] - X_ptr[r], axis=0)
                                       for j, r in enumerate(idx)])
                uniq, inv = np.unique(все, return_inverse=True)
                gE = np.zeros((len(uniq), D))
                np.add.at(gE, inv, повт)
                gE += лямбда * E[uniq]
                mE[uniq] = b1 * mE[uniq] + (1 - b1) * gE
                vE[uniq] = b2 * vE[uniq] + (1 - b2) * gE * gE
                E[uniq] -= lr * (mE[uniq] / (1 - b1 ** t)) / (np.sqrt(vE[uniq] / (1 - b2 ** t)) + eps)
    U = np.concatenate([Uq, Us], axis=1)
    b = np.concatenate([bq, bs])
    return E.astype(np.float32), U.astype(np.float32), b.astype(np.float32)


def предсказать(E, U, b, X_idx, X_ptr, rows):
    Yq = len(ВОПРОС_КЛАССЫ)
    Uq, Us = U[:, :Yq], U[:, Yq:]
    bq, bs = b[:Yq], b[Yq:]
    n = len(rows)
    h = np.zeros((n, D))
    lens = np.zeros(n)
    for j in range(n):
        a, bb = X_ptr[j], X_ptr[j + 1]
        ii = X_idx[a:bb]
        lens[j] = max(1, len(ii))
        if len(ii):
            h[j] = E[ii].astype(np.float64).sum(0)
    h = h / np.sqrt(lens)[:, None]
    sq = h @ Uq.astype(np.float64) + bq
    ss = h @ Us.astype(np.float64) + bs
    return sq, ss


def метрики(y_true, scores, имена):
    pred = np.asarray(scores).argmax(1)
    acc = float((pred == np.asarray(y_true)).mean()) if len(y_true) else 0.0
    f1s = []
    for c in range(len(имена)):
        tp = int(((pred == c) & (np.asarray(y_true) == c)).sum())
        fp = int(((pred == c) & (np.asarray(y_true) != c)).sum())
        fn = int(((pred != c) & (np.asarray(y_true) == c)).sum())
        f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    macro = float(np.mean(f1s))
    return acc, macro, pred, f1s


def ece(y_true, scores, корзин=10):
    p = softmax(np.asarray(scores, dtype=np.float64))
    conf = p.max(1)
    pred = p.argmax(1)
    верн = (pred == np.asarray(y_true))
    e = 0.0
    for k in range(корзин):
        lo, hi = k / корзин, (k + 1) / корзин
        m = (conf > lo) & (conf <= hi) if k else (conf <= hi)
        if m.sum():
            e += abs(верн[m].mean() - conf[m].mean()) * m.sum() / len(y_true)
    return float(e)


def кривая(y_true, scores, пороги=(0.0, 0.5, 1.0, 1.5, 2.0, 3.0)):
    s = np.asarray(scores, dtype=np.float64)
    о = np.sort(s, axis=1)[:, ::-1]
    margin = о[:, 0] - о[:, 1]
    pred = s.argmax(1)
    верн = (pred == np.asarray(y_true))
    out = []
    for tau in пороги:
        m = margin >= tau
        n_ans = int(m.sum())
        out.append({"порог": tau, "отвечено": n_ans, "всего": len(y_true),
                    "покрытие": round(n_ans / len(y_true), 4) if len(y_true) else 0.0,
                    "точность": round(float(верн[m].mean()) if n_ans else 0.0, 4)})
    return out


ШАБЛОНЫ_СТИЛЯ = {
    "что_делать": ("Совет сообщества — что делать:", "Спокойно, по шагам: опиши ситуацию своими словами, собери бумаги заранее, иди и задавай вопросы письменно. Отвечай дружелюбно и по делу, без паники."),
    "можно_ли": ("Совет сообщества — можно ли:", "Коротко и прямо: да/нет зависит от бумаг и порядка. Уточни детали (когда, где, что на руках) и требуй письменный ответ."),
    "как_оформить": ("Совет сообщества — как оформить:", "По порядку: 1) заявление в двух экземплярах, 2) копии приложи, на втором отметка о приеме, 3) жди ответ в срок. Все устно сказанное проси продублировать письменно."),
    "боюсь": ("Поддержка сообщества:", "Не переживай, такое бывает у многих. Расскажи, что именно тревожит, — подскажем по шагам. Держись, ты не один."),
    "правда_ли": ("Разбор слуха:", "Не верь на слово: слухи проверяются по первоисточнику. Спроси, где человек это взял, и сверь с официальным порядком."),
    "куда_обратиться": ("Куда обратиться:", "Иди туда, где принимают решения и ставят отметки: канцелярия/приемная с входящим номером. Параллельно — горячая линия профильного ведомства."),
    "уточнение": ("Уточнение:", "Уточни детали: даты, место, что уже сделано и что на руках. Чем точнее вопрос — тем точнее совет."),
    "поделиться": ("Спасибо, что поделился:", "Принято. Если хочешь совета — задай конкретный вопрос, а так держись, бывает."),
}


def собрать_шаблоны(ответы):
    ш = {}
    for a in ответы:
        if ":вопрос_" in a:
            ключ = a.split(":вопрос_")[-1]
            з, т = ШАБЛОНЫ_СТИЛЯ.get(ключ, ("Совет сообщества:", "Отвечай дружелюбно и по делу."))
            ш[a] = {"заголовок": "💬 " + з, "текст": т}
        elif ":стиль_" in a:
            ключ = a.split(":стиль_")[-1]
            тексты = {
                "вопрос_в_ответ": "Уточни у человека детали одним вопросом — так принято в сообществе, когда мало данных.",
                "ссылка_на_норму": "Коротко сошлись на порядок и пункт: так отвечает сообщество, когда спрашивают про правила.",
                "личный_опыт": "Поделись своим случаем коротко: у меня было так-то, сделал так-то, итог такой.",
                "эмоциональный": "Ответь тепло и неформально, поддержи человека, без канцелярита.",
                "короткий_прямой": "Ответь коротко и прямо, одним-двумя предложениями.",
                "подробный_деловой": "Ответь подробно и по шагам, дружелюбно, с конкретными действиями.",
            }
            ш[a] = {"заголовок": "💬 Стиль сообщества:", "текст": тексты.get(ключ, "Отвечай дружелюбно и по делу.")}
    return ш


def main():
    зерно = int(sys.argv[sys.argv.index("--зерно") + 1]) if "--зерно" in sys.argv else ЗЕРНО_ПО_УМОЛЧАНИЮ
    быстро = "--быстро" in sys.argv
    rng = np.random.RandomState(зерно)
    t0 = __import__("time").time()

    лимит = {"армия": 12000, "ключи": 6000, "право": 12000, "болезни": 12000, "фон": 20000} if быстро else \
            {"армия": 22000, "ключи": 10000, "право": 20000, "болезни": 20000, "фон": 30000}
    сырые, просканировано, отобрано_файлов, счет_кат = загрузить_строки(лимит)
    print("загружено сырых: %d (файлов прочитано %d, просканировано %d записей в %d чанках)" % (
        len(сырые), отобрано_файлов, просканировано, len(ЧАНКИ)), flush=True)
    print("по категориям файлов: %s" % (счет_кат,), flush=True)

    # слабая разметка
    данные = []
    for r in сырые:
        полный = r["текст"]
        q = разметить_вопрос(полный)
        s = разметить_стиль(r["лучший"], r["ответы"])
        данные.append({"qid": r["qid"], "кат": r["файл_кат"], "текст": полный, "вопрос": q, "стиль": s})

    # деление по qid
    train, dev, test = [], [], []
    for r in данные:
        d = qid_доля(r["qid"])
        if d < 0.8:
            train.append(r)
        elif d < 0.9:
            dev.append(r)
        else:
            test.append(r)
    print("split по qid: train %d dev %d test %d" % (len(train), len(dev), len(test)), flush=True)

    # доли классов
    from collections import Counter
    print("вопрос train: %s" % (dict(Counter(r["вопрос"] for r in train)),), flush=True)
    ст_тр = [r["стиль"] for r in train if r["стиль"]]
    print("стиль train (только с ответом): %d %s" % (len(ст_тр), dict(Counter(ст_тр))), flush=True)

    # 50 примеров для ручной проверки — сохраняем отдельно
    rng50 = np.random.RandomState(зерно + 7)
    idx50 = rng50.choice(len(test), size=min(50, len(test)), replace=False)
    проверка = []
    for i in idx50:
        r = test[int(i)]
        проверка.append({"qid": r["qid"], "кат": r["кат"], "текст": r["текст"][:600],
                         "слабая_вопрос": r["вопрос"], "слабый_стиль": r["стиль"]})
    осн = os.path.join(V8, "обучение", "мейлру_проверка50.jsonl")
    with open(осн, "w", encoding="utf-8") as f:
        for r in проверка:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("50 примеров для ручной проверки: %s" % осн, flush=True)

    qi = {н: i for i, н in enumerate(ВОПРОС_КЛАССЫ)}
    si = {н: i for i, н in enumerate(СТИЛЬ_КЛАССЫ)}

    def подготовить(набор, маскировать_ли):
        X_idx_list, X_ptr = [], [0]
        yq, ys = [], []
        for r in набор:
            текст = маскировать(r["текст"]) if маскировать_ли else r["текст"]
            токс = токены_текста(текст)
            ii = [индекс(t) for t in токс]
            X_idx_list.extend(ii)
            X_ptr.append(X_ptr[-1] + len(ii))
            yq.append(qi[r["вопрос"]])
            ys.append(si[r["стиль"]] if r["стиль"] else -1)
        return (np.array(X_idx_list, dtype=np.int64), np.array(X_ptr, dtype=np.int64),
                np.array(yq, dtype=np.int64), np.array(ys, dtype=np.int64))

    print("токенизация train (маскированная)...", flush=True)
    tr_idx, tr_ptr, tr_yq, tr_ys = подготовить(train, True)
    print("токенизация dev/test...", flush=True)
    dv_idx, dv_ptr, dv_yq, dv_ys = подготовить(dev, True)
    te_idx, te_ptr, te_yq, te_ys = подготовить(test, True)
    te_idx_raw, te_ptr_raw, _, _ = подготовить(test, False)
    print("токены: train %d dev %d test %d (%.0f c)" % (
        len(tr_idx), len(dv_idx), len(te_idx), __import__("time").time() - t0), flush=True)

    # обучение (маскированная версия — основная)
    print("обучение совместное (зерно %d, эпох 12)... " % зерно, flush=True)
    E, U, b = обучить_совместно(tr_idx, tr_ptr, tr_yq, tr_ys, len(ВОПРОС_КЛАССЫ), len(СТИЛЬ_КЛАССЫ), seed=зерно)
    sq_dv, ss_dv = предсказать(E, U, b, dv_idx, dv_ptr, dev)
    acc_q, f1_q, _, _ = метрики(dv_yq, sq_dv, ВОПРОС_КЛАССЫ)
    м_ст = dv_ys >= 0
    acc_s, f1_s, _, _ = метрики(dv_ys[м_ст], ss_dv[м_ст], СТИЛЬ_КЛАССЫ)
    print("dev masked: вопрос acc %.4f macroF1 %.4f | стиль acc %.4f macroF1 %.4f (n_стиль=%d)" % (
        acc_q, f1_q, acc_s, f1_s, int(м_ст.sum())), flush=True)

    # версия без маскировки (тот же сид, те же сплиты) — для проверки зависимости от тем
    print("токенизация train без маски + обучение без маски...", flush=True)
    tr2_idx, tr2_ptr, _, _ = подготовить(train, False)
    E2, U2, b2 = обучить_совместно(tr2_idx, tr2_ptr, tr_yq, tr_ys, len(ВОПРОС_КЛАССЫ), len(СТИЛЬ_КЛАССЫ), seed=зерно)
    sq2, ss2 = предсказать(E2, U2, b2, te_idx_raw, te_ptr_raw, test)
    sq, ss = предсказать(E, U, b, te_idx, te_ptr, test)
    acc_q_m, f1_q_m, pred_q, f1s_q = метрики(te_yq, sq, ВОПРОС_КЛАССЫ)
    м = te_ys >= 0
    acc_s_m, f1_s_m, pred_s, f1s_s = метрики(te_ys[м], ss[м], СТИЛЬ_КЛАССЫ)
    acc_q_u, f1_q_u, _, _ = метрики(te_yq, sq2, ВОПРОС_КЛАССЫ)
    acc_s_u, f1_s_u, _, _ = метрики(te_ys[м], ss2[м], СТИЛЬ_КЛАССЫ)
    print("test MASKED: вопрос acc %.4f F1 %.4f | стиль acc %.4f F1 %.4f" % (acc_q_m, f1_q_m, acc_s_m, f1_s_m), flush=True)
    print("test UNMASKED: вопрос acc %.4f F1 %.4f | стиль acc %.4f F1 %.4f" % (acc_q_u, f1_q_u, acc_s_u, f1_s_u), flush=True)
    print("дельта маскировки: вопрос %+.4f acc %+.4f F1 | стиль %+.4f acc %+.4f F1" % (
        acc_q_m - acc_q_u, f1_q_m - f1_q_u, acc_s_m - acc_s_u, f1_s_m - f1_s_u), flush=True)

    # базовые линии на test
    from collections import Counter as C
    част_q = C(tr_yq).most_common(1)[0][0]
    част_s = C([int(x) for x in tr_ys if x >= 0]).most_common(1)[0][0]
    base_maj_q = np.zeros_like(sq)
    base_maj_q[:, част_q] = 1.0
    base_maj_s = np.zeros_like(ss)
    base_maj_s[:, част_s] = 1.0
    a_maj_q, f_maj_q, _, _ = метрики(te_yq, base_maj_q[:, :len(ВОПРОС_КЛАССЫ)], ВОПРОС_КЛАССЫ)
    a_maj_s, f_maj_s, _, _ = метрики(te_ys[м], base_maj_s[м][:, :len(СТИЛЬ_КЛАССЫ)], СТИЛЬ_КЛАССЫ)
    # ключевые слова (бедные)
    kb_q = np.array([qi[база_ключевые_вопрос(r["текст"])] for r in test])
    kb_s = np.array([si[база_ключевой_стиль(маскировать(r["текст"]))] for r in test])
    a_kb_q = float((kb_q == te_yq).mean())
    a_kb_s = float((kb_s[м] == te_ys[м]).mean())

    def macro_f1(yt, yp, n):
        f = []
        yt = np.asarray(yt)
        yp = np.asarray(yp)
        for c in range(n):
            tp = int(((yp == c) & (yt == c)).sum())
            fp = int(((yp == c) & (yt != c)).sum())
            fn = int(((yp != c) & (yt == c)).sum())
            f.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
        return float(np.mean(f))

    f_kb_q = macro_f1(te_yq, kb_q, len(ВОПРОС_КЛАССЫ))
    f_kb_s = macro_f1(te_ys[м], kb_s[м], len(СТИЛЬ_КЛАССЫ))
    # случайные веса (нынешний блок)
    rng_r = np.random.RandomState(42)
    Er = (rng_r.randn(B, D) * 0.05).astype(np.float32)
    Ur = (rng_r.randn(D, len(ВОПРОС_КЛАССЫ) + len(СТИЛЬ_КЛАССЫ)) * 0.05).astype(np.float32)
    br = np.zeros(len(ВОПРОС_КЛАССЫ) + len(СТИЛЬ_КЛАССЫ), np.float32)
    sqr, ssr = предсказать(Er, Ur, br, te_idx, te_ptr, test)
    a_r_q, f_r_q, _, _ = метрики(te_yq, sqr, ВОПРОС_КЛАССЫ)
    a_r_s, f_r_s, _, _ = метрики(te_ys[м], ssr[м], СТИЛЬ_КЛАССЫ)

    print("БАЗА majority: вопрос acc %.4f F1 %.4f | стиль acc %.4f F1 %.4f" % (a_maj_q, f_maj_q, a_maj_s, f_maj_s), flush=True)
    print("БАЗА keywords: вопрос acc %.4f F1 %.4f | стиль acc %.4f F1 %.4f" % (a_kb_q, f_kb_q, a_kb_s, f_kb_s), flush=True)
    print("БАЗА random: вопрос acc %.4f F1 %.4f | стиль acc %.4f F1 %.4f" % (a_r_q, f_r_q, a_r_s, f_r_s), flush=True)

    # калибровка и селективность (маскированная модель)
    print("ECE вопрос %.4f стиль %.4f" % (ece(te_yq, sq), ece(te_ys[м], ss[м])), flush=True)
    print("кривая вопрос: %s" % (кривая(te_yq, sq),), flush=True)
    print("кривая стиль: %s" % (кривая(te_ys[м], ss[м]),), flush=True)

    # топ-токены на класс (проверка отсутствия тематики): смотрим argmax |U| по корзинам нельзя
    # инвертировать, поэтому проверяем веса частых тематических токенов напрямую.
    пров = ["с:военкомат", "с:призыв", "с:армия", "с:повестка", "с:ввк", "с:отсрочка", "с:годность"]
    print("проверка тематических токенов (норма эмбеддинга):", flush=True)
    for t in пров:
        ii = индекс(t)
        print("  %s idx %d ||E||=%.3f" % (t, ii, float(np.linalg.norm(E[ii]))), flush=True)

    # упаковка весов
    ответы = ["ответ:мейлру:вопрос_%s" % н for н in ВОПРОС_КЛАССЫ] + \
             ["ответ:мейлру:стиль_%s" % н for н in СТИЛЬ_КЛАССЫ]
    пишет = ["вывод_ответы_мейлру", "стиль:живой_ответ"]
    читает = ["вывод_ответы_мейлру"]
    Y = len(ответы)
    R = len(читает)
    V = np.zeros((2 * R, Y), dtype=np.float32)
    шаблоны = собрать_шаблоны(ответы)
    npz = os.path.join(ПАПКА_БЛОКА, "веса.npz")
    np.savez_compressed(npz, E=E, U=U, b=b, V=V,
                        ответы=np.array(ответы), пишет=np.array(пишет),
                        читает=np.array(читает),
                        шаблоны_json=np.array(json.dumps(шаблоны, ensure_ascii=False)))
    sha = hashlib.sha256(open(npz, "rb").read()).hexdigest()
    чисел = int(E.size + U.size + b.size + V.size)
    паспорт = {
        "имя": "ответы_мейлру",
        "версия": 2,
        "роль": "стиль живого ответа и тип вопроса (без темы)",
        "область": "стиль",
        "архитектура": "живой_стиль",
        "настройки": {"корзины": B, "размер": D, "соль": СОЛЬ, "масштаб_чтения": МАСШТАБ},
        "веса": {"файл": "веса.npz", "sha256": sha, "чисел": чисел},
        "язык": {"имя": "NNL-1", "версия": "1.1",
                 "правила": "40564480803950740e1728adf1985fd0f24fee01bf348a9047f8fdf1a6506184",
                 "ответы": "d95f5843858c35e79bc0504e4f42b63fab93e27e9c6f2cfaff02982b4dfd6b2d",
                 "понятия": {k: "hash" for k in пишет + читает}},
        "пишет": пишет,
        "читает": читает,
        "ответы": ответы,
        "проекции": {a: {"стиль:живой_ответ": 16.0} for a in ответы},
        "обучение": {
            "скрипт": "v8/обучение/обучить_мейлру.py",
            "зерно": зерно,
            "когда": datetime.datetime.now().isoformat(timespec="seconds"),
            "версия": 2,
            "данные": "otvetmailru CC0 (its5Q), чанки %s" % (",".join(ЧАНКИ),),
            "просканировано_записей": просканировано,
            "файлов_прочитано_строк": отобрано_файлов,
            "взято_строк": len(сырые),
            "train": len(train),
            "dev": len(dev),
            "test": len(test),
            "маскировка": "тематика (военкомат/призыв/армия/повестка/ВВК/болезни/статьи) заменена пробелом",
            "эпох": 12,
            "dev_вопрос_acc": round(acc_q, 4),
            "dev_стиль_acc": round(acc_s, 4),
        },
    }
    json.dump(паспорт, open(os.path.join(ПАПКА_БЛОКА, "паспорт.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("сохранено: %s (чисел %d, sha %s...)" % (npz, чисел, sha[:12]), flush=True)

    таблица = {
        "test_n": len(test),
        "вопрос": {
            "majority": {"acc": round(a_maj_q, 4), "F1": round(f_maj_q, 4)},
            "keywords": {"acc": round(a_kb_q, 4), "F1": round(f_kb_q, 4)},
            "random": {"acc": round(a_r_q, 4), "F1": round(f_r_q, 4)},
            "unmasked": {"acc": round(acc_q_u, 4), "F1": round(f1_q_u, 4)},
            "masked_обученный": {"acc": round(acc_q_m, 4), "F1": round(f1_q_m, 4)},
        },
        "стиль": {
            "majority": {"acc": round(a_maj_s, 4), "F1": round(f_maj_s, 4)},
            "keywords": {"acc": round(a_kb_s, 4), "F1": round(f_kb_s, 4)},
            "random": {"acc": round(a_r_s, 4), "F1": round(f_r_s, 4)},
            "unmasked": {"acc": round(acc_s_u, 4), "F1": round(f1_s_u, 4)},
            "masked_обученный": {"acc": round(acc_s_m, 4), "F1": round(f1_s_m, 4)},
        },
        "ece_вопрос": round(ece(te_yq, sq), 4),
        "ece_стиль": round(ece(te_ys[м], ss[м]), 4),
        "f1_по_классам_вопрос": {н: round(v, 4) for н, v in zip(ВОПРОС_КЛАССЫ, f1s_q)},
        "f1_по_классам_стиль": {н: round(v, 4) for н, v in zip(СТИЛЬ_КЛАССЫ, f1s_s)},
        "доли_вопрос_test": {н: int((te_yq == i).sum()) for i, н in enumerate(ВОПРОС_КЛАССЫ)},
        "доли_стиль_test": {н: int((te_ys[м] == i).sum()) for i, н in enumerate(СТИЛЬ_КЛАССЫ)},
    }
    json.dump(таблица, open(os.path.join(V8, "обучение", "мейлру_таблица.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps(таблица, ensure_ascii=False, indent=2))
    print("готово за %.0f c" % (__import__("time").time() - t0), flush=True)


if __name__ == "__main__":
    main()
