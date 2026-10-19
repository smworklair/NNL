# -*- coding: utf-8 -*-
"""Отрицание в тексте вопроса — правила, без обученных чисел (по образцу NegEx: слово-отрицание + область действия).

Ядро не знает, о чём вопрос. Оно только находит, что человек ОТРИЦАЕТ («у меня нет астмы», «астмы не было»,
«не болел гастритом»), и по просьбе блока убирает отрицаемое из текста, прежде чем отдать текст блоку.
Просит блок сам — полем паспорта «отрицание»: {"поле": "текст", "кроме": [основы слов]}. «кроме» — то, отсутствие чего для
блока само является признаком («нет пальца», «ушной раковины нет»): такие места не убираются.

Слово-отрицание действует вперёд («нет астмы»), а если за ним сразу граница — назад («астмы нет»), не дальше 4 слов и не
через границу (знак препинания, «но», «а», «однако», «зато», «хотя», «только», «есть», «кроме»).
Не считаются отрицанием: «или нет», «нет ли», «нет» в начале фразы перед запятой («нет, у меня…»).
Предлог «без» не используется: «без очков», «без последствий», «без глаза» — слишком разные смыслы."""
import re

TRIGGERS = [t.split() for t in (
    "никогда не было", "никогда не болел", "никогда не болела",
    "не было", "не бывало", "не болел", "не болела", "не болею", "не болеет", "не болели", "не страдаю", "не страдал",
    "не страдала", "не страдает", "не имею", "не имел", "не выявили", "не выявлено", "не выявлен", "не выявлена",
    "не обнаружили", "не обнаружено", "не обнаружен", "не обнаружена", "не нашли", "не находили", "не ставили",
    "не поставили", "не подтвердили", "не подтвердился", "не подтвердилось", "не подтвердилась", "не диагностировали",
    "нет", "нету", "отсутствует", "отсутствуют", "исключили", "исключен", "исключена")]
TRIGGERS.sort(key=len, reverse=True)
BOUNDARY_WORDS = frozenset("но а однако зато хотя только есть кроме".split())
SCOPE = 4
_TOK = re.compile(r"[а-яёa-z0-9]+|[^\sа-яёa-z0-9]")


def _tokens(text):
    return [(m.group(0), m.start(), m.end()) for m in _TOK.finditer(text.lower())]


def _is_word(tok):
    return tok[0][0].isalnum()


def _boundary(tok):
    return not _is_word(tok) or tok[0] in BOUNDARY_WORDS


def negations(text):
    """Найденные отрицания: [{"отрицание": слова, "что": отрицаемые слова, "куда": "вперёд"|"назад", "места": [(start, end)]}]."""
    toks = _tokens(text)
    out, i, n = [], 0, len(toks)
    while i < n:
        hit = next((t for t in TRIGGERS if [x[0] for x in toks[i:i + len(t)]] == t), None)
        if hit is None:
            i += 1
            continue
        j = i + len(hit)
        prev = toks[i - 1] if i > 0 else None
        nxt = toks[j] if j < n else None
        if hit == ["нет"] and ((prev and prev[0] == "или") or (nxt and nxt[0] == "ли")
                               or ((prev is None or not _is_word(prev)) and nxt is not None and not _is_word(nxt))):
            i = j
            continue
        scope = []
        if nxt is not None and not _boundary(nxt):
            k = j
            while k < n and len(scope) < SCOPE and not _boundary(toks[k]) and not any(
                    [x[0] for x in toks[k:k + len(t)]] == t for t in TRIGGERS):
                scope.append(toks[k])
                k += 1
            way = "вперёд"
        else:
            k = i - 1
            while k >= 0 and len(scope) < SCOPE and not _boundary(toks[k]):
                scope.insert(0, toks[k])
                k -= 1
            way = "назад"
        if scope:
            out.append({"отрицание": " ".join(x[0] for x in toks[i:j]), "что": " ".join(x[0] for x in scope), "куда": way,
                        "места": [(x[1], x[2]) for x in toks[i:j]] + [(x[1], x[2]) for x in scope]})
        i = j
    return out


def strip_negated(text, keep=()):
    """Текст без отрицаемого. keep — основы слов, отсутствие которых само признак: такие отрицания не трогаются.
    Возвращает (новый текст, [убранные отрицания], [оставленные из-за keep])."""
    keep = tuple(k.lower() for k in keep)
    removed, kept, spans = [], [], []
    for neg in negations(text):
        if keep and any(w.startswith(keep) for w in neg["что"].split()):
            kept.append(neg["отрицание"] + " · " + neg["что"])
            continue
        removed.append(neg["отрицание"] + " · " + neg["что"])
        spans += neg["места"]
    if not spans:
        return text, removed, kept
    mask = [False] * len(text)
    for a, b in spans:
        for p in range(a, b):
            mask[p] = True
    new = "".join(" " if m else c for c, m in zip(text, mask))
    new = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s{2,}", " ", new)).strip()
    return new, removed, kept
