# -*- coding: utf-8 -*-
"""Разбор текста в признаки — код архитектуры (не ядра, не типов). Обученных чисел нет.
Слова: нижний регистр, ё→е, куски из букв и цифр; служебные слова выбрасываются; основа — Snowball (русский).
Признаки по хешу: основы (u:), пары основ (b:), куски слов 3–5 букв (c:)."""
import re
import zlib

import snowballstemmer

STOP = frozenset("""
и в во на с со к ко о об обо от до по за из изо у а но да или либо ли же бы б ведь вот ну то это этот эта эти этого этой
этим этих тот та те того той тем тех так как что чтобы когда где куда откуда если чем при для под над про через между
я мы ты вы он она оно они меня мне мной нас нам нами тебя тебе тобой вас вам вами его ему им её ее ей ею их ими него нему
нем нём ней нее неё них ним ними мой моя мое моё мои моего моей моему моим моих свой своя свое своё свои своего своей
своему своим своих себя себе собой твой твоя твое твоё твои ваш ваша ваше ваши наш наша наше наши уже ещё еще тоже также
даже лишь вообще просто типа нибудь
""".split())
_WORD = re.compile(r"[а-яa-z0-9]+")
_stem = snowballstemmer.stemmer("russian")


def h(s, buckets):
    return zlib.crc32(s.encode("utf-8")) % buckets


def content_words(text):
    return [w for w in _WORD.findall(text.lower().replace("ё", "е")) if w not in STOP]


def features(text, buckets):
    ws = content_words(text)
    st = [_stem.stemWord(w) for w in ws]
    idx = [h("u:" + s, buckets) for s in st]
    idx += [h("b:%s|%s" % (a, b), buckets) for a, b in zip(st, st[1:])]
    for w in ws:
        g = "<" + w + ">"
        idx += [h("c:" + g[i:i + n], buckets) for n in (3, 4, 5) for i in range(len(g) - n + 1)]
    return idx
