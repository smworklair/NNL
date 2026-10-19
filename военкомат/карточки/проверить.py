# -*- coding: utf-8 -*-
"""Проверка карточек статей: каждая цитата должна быть дословно в тексте статьи, числа порогов должны стоять в цитате правила,
буквы пунктов должны существовать, ссылки на другие статьи должны быть и стоять в цитате. Придуманному здесь не пройти.
Запуск: python проверить.py [ид ...]     (без аргументов — все файлы из данные/)
Код возврата 0 — ошибок нет (предупреждения допустимы)."""
import json
import os
import re
import sys

sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(ЗДЕСЬ)), "NNL", "диалог"))   # знания.py лежат в ядре диалога
import знания as З  # noqa: E402

ДАННЫЕ = os.path.join(ЗДЕСЬ, "данные")
ВИДЫ = {"чеклист", "ползунок", "признаки", "исключение"}


def норм(с):
    с = (с or "").lower().replace("ё", "е")
    for к in "«»“”„‟\"'":
        с = с.replace(к, '"')
    for к in "—–−‑":
        с = с.replace(к, "-")
    с = с.replace("|", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", с).strip()


def _ч(x):
    return "{:g}".format(float(str(x).replace(",", ".")))


def числа_в(с):
    return {_ч(x) for x in re.findall(r"\d+(?:[.,]\d+)?", с or "")}


def проверить_файл(ид, д, база):
    ош, пред = [], []
    а = база.статьи.get(ид)
    if а is None:
        return ["нет статьи %s в базе" % ид], []
    текст = норм(а.сырой + " " + " ".join(а.примечания) + " " + " ".join(str(п) for п in а.пункты))
    текст = текст.split("открыть полный текст документа")[0]          # мусор с сайта-источника в источник цитат не входит
    буквы = set()
    for п in а.пункты:
        б = п.get("буква") if isinstance(п, dict) else getattr(п, "буква", "")
        if б:
            буквы.add(б)

    def цитата_ок(ц, где):
        if not ц or len(норм(ц)) < 12:
            ош.append("%s: цитата пустая или короче 12 знаков" % где)
            return False
        if "…" in ц or "..." in ц:
            ош.append("%s: в цитате многоточие, нужна сплошная цитата" % где)
            return False
        if норм(ц) not in текст:
            ош.append("%s: цитаты нет в тексте статьи: «%s»" % (где, ц[:90]))
            return False
        if len(ц) > 450:
            пред.append("%s: цитата длиннее 450 знаков" % где)
        return True

    if str(д.get("ид")) != ид:
        ош.append("поле ид не совпадает с файлом")
    if д.get("статус") not in ("черновик", "проверено"):
        ош.append("статус должен быть «черновик» или «проверено»")
    блоки = д.get("блоки")
    if not isinstance(блоки, list):
        return ош + ["нет списка блоков"], пред
    for i, б in enumerate(блоки):
        где = "блок %d (%s)" % (i + 1, б.get("вид"))
        вид = б.get("вид")
        if вид not in ВИДЫ:
            ош.append("%s: неизвестный вид" % где)
            continue
        if not б.get("заг"):
            ош.append("%s: нет заголовка" % где)
        if вид == "чеклист":
            if not б.get("пункты"):
                ош.append("%s: нет пунктов" % где)
            for j, п in enumerate(б.get("пункты", [])):
                if not п.get("текст"):
                    ош.append("%s, пункт %d: нет текста" % (где, j + 1))
                цитата_ок(п.get("цитата"), "%s, пункт %d" % (где, j + 1))
        elif вид == "ползунок":
            поля = {п["ключ"]: п for п in б.get("поля", []) if "ключ" in п}
            if not поля:
                ош.append("%s: нет полей" % где)
            for к, п in поля.items():
                for н in ("подпись", "ед", "мин", "макс", "шаг", "знач"):
                    if н not in п:
                        ош.append("%s, поле %s: нет «%s»" % (где, к, н))
                if all(н in п for н in ("мин", "макс", "знач")) and not (п["мин"] <= п["знач"] <= п["макс"]):
                    ош.append("%s, поле %s: значение вне диапазона" % (где, к))
            if not б.get("правила"):
                ош.append("%s: нет правил" % где)
            for j, р in enumerate(б.get("правила", [])):
                гд = "%s, правило %d" % (где, j + 1)
                if р.get("пункт") not in буквы:
                    ош.append("%s: пункта «%s» нет в статье (есть: %s)" % (гд, р.get("пункт"), ", ".join(sorted(буквы))))
                ц = р.get("цитата")
                if цитата_ок(ц, гд):
                    нужные = set()
                    for к, у in (р.get("когда") or {}).items():
                        if к not in поля:
                            ош.append("%s: нет поля «%s»" % (гд, к))
                        for гр in ("от", "до", "больше", "меньше"):
                            if гр in у:
                                нужные.add(_ч(у[гр]))
                    нет = {x for x in нужные if x not in числа_в(ц)}
                    if нет:
                        ош.append("%s: числа %s из условия нет в цитате правила" % (гд, ", ".join(sorted(нет))))
        elif вид == "признаки":
            if not б.get("варианты"):
                ош.append("%s: нет вариантов" % где)
            for j, в in enumerate(б.get("варианты", [])):
                гд = "%s, вариант %d" % (где, j + 1)
                if not в.get("текст"):
                    ош.append("%s: нет текста" % гд)
                if в.get("пункт") is not None and в.get("пункт") not in буквы:
                    ош.append("%s: пункта «%s» нет в статье (есть: %s)" % (гд, в.get("пункт"), ", ".join(sorted(буквы))))
                цитата_ок(в.get("цитата"), гд)
        elif вид == "исключение":
            ст = str(б.get("статья", ""))
            if ст not in база.статьи:
                ош.append("%s: статьи %s нет" % (где, ст))
            if not б.get("текст"):
                ош.append("%s: нет текста" % где)
            if цитата_ок(б.get("цитата"), где) and ст and ст not in числа_в(б.get("цитата")):
                ош.append("%s: номера статьи %s нет в цитате" % (где, ст))
    return ош, пред


def main(ид_список):
    база = З.База()
    файлы = sorted(f for f in os.listdir(ДАННЫЕ) if f.endswith(".json"))
    if ид_список:
        файлы = [f for f in файлы if f[:-5] in ид_список]
    всего_ош = 0
    for ф in файлы:
        ид = ф[:-5]
        try:
            д = json.load(open(os.path.join(ДАННЫЕ, ф), encoding="utf-8"))
        except ValueError as е:
            print("ст. %s: НЕ JSON: %s" % (ид, е))
            всего_ош += 1
            continue
        ош, пред = проверить_файл(ид, д, база)
        всего_ош += len(ош)
        if ош or пред:
            print("ст. %s:" % ид)
            for о in ош:
                print("   ОШИБКА  " + о)
            for п in пред:
                print("   внимание  " + п)
    print("\nкарточек проверено: %d, ошибок: %d" % (len(файлы), всего_ош))
    return 1 if всего_ош else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
