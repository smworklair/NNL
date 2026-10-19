# -*- coding: utf-8 -*-
"""NNL (Neural Network Lego) — Утилита валидации блока (NNL Linter / Checker).

Проверяет соответствие папки блока стандарту NNL v1.0:
  1. Наличие и валидность паспорт.json.
  2. Соответствие контрольной суммы sha256 файла весов.
  3. Совместимость с кодом объявленной архитектуры.
  4. Тест контракта изоляции (проход при пустом срезе шины).

Запуск:
  python NNL/линтер.py <путь_к_папке_блока> [путь_к_папке_архитектур]
"""
import hashlib
import importlib.util
import json
import os
import sys

ОБЯЗАТЕЛЬНО = ("имя", "версия", "архитектура", "веса", "пишет", "читает", "ответы")


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def проверить_блок(папка_блока, папка_архитектур=None):
    ошибки = []
    предупреждения = []
    папка_блока = os.path.abspath(папка_блока)

    # 1. Проверка паспорт.json
    пасп_файл = os.path.join(папка_блока, "паспорт.json")
    if not os.path.isfile(пасп_файл):
        return {"статус": "ОШИБКА", "ошибки": [f"Файл {пасп_файл} не найден"]}

    try:
        with open(пасп_файл, encoding="utf-8") as f:
            пасп = json.load(f)
    except Exception as e:
        return {"статус": "ОШИБКА", "ошибки": [f"Ошибка парсинга JSON: {e}"]}

    for поле in ОБЯЗАТЕЛЬНО:
        if поле not in пасп:
            ошибки.append(f"Отсутствует обязательное поле {поле!r} в паспорте")

    if ошибки:
        return {"статус": "ОШИБКА", "ошибки": ошибки}

    # 2. Проверка файла весов
    веса_cfg = пасп.get("веса", {})
    вес_файл = os.path.join(папка_блока, веса_cfg.get("файл", ""))
    if not os.path.isfile(вес_файл):
        ошибки.append(f"Файл весов {вес_файл!r} не существует")
    else:
        sha_факт = _sha256_file(вес_файл)
        sha_паспорт = веса_cfg.get("sha256")
        if sha_факт != sha_паспорт:
            ошибки.append(f"Несовпадение sha256 весов: в паспорте {sha_паспорт}, на диске {sha_факт}")

    # 3. Проверка архитектуры
    arch_имя = пасп.get("архитектура")
    if папка_архитектур:
        arch_путь = os.path.join(папка_архитектур, arch_имя + ".py")
    else:
        # Ищем по умолчанию в v8/архитектуры
        корень = os.path.dirname(os.path.dirname(папка_блока))
        arch_путь = os.path.join(корень, "система", "архитектуры", arch_имя + ".py")

    if not os.path.isfile(arch_путь):
        ошибки.append(f"Код архитектуры {arch_имя!r} не найден по пути {arch_путь}")
        obj = None
        arch_mod = None
    else:
        try:
            arch_mod = _load_module(arch_путь, f"lint_arch_{arch_имя}")
            for метод in ("загрузить", "чисел", "проход2"):
                if not hasattr(arch_mod, метод):
                    ошибки.append(f"В модуле архитектуры {arch_имя} отсутствует обязательный метод {метод}")
            if not ошибки:
                obj = arch_mod.загрузить(вес_файл, пасп)
            else:
                obj = None
        except Exception as e:
            ошибки.append(f"Ошибка загрузки блока архитектурой {arch_имя}: {e}")
            obj = None
            arch_mod = None

    # 4. Проверка контракта изоляции
    if obj is not None and arch_mod is not None:
        try:
            тест_токены = ["тест", "проверка", "блок"]
            счёт_изоляция = arch_mod.проход2(obj, тест_токены, {})
            if not isinstance(счёт_изоляция, dict) or len(счёт_изоляция) == 0:
                ошибки.append("Метод проход2 вернул пустой или некорректный словарь счетов при изолированном срезе {}")
        except Exception as e:
            ошибки.append(f"Сбой выполнения проход2 в изолированном режиме: {e}")

    # 5. Проверка объявленных проекций
    if "проекции" not in пасп:
        предупреждения.append("В паспорте нет поля 'проекции'. Блок будет использовать внешнюю онтологию.")

    статус = "УСПЕХ" if not ошибки else "ОШИБКА"
    return {
        "статус": статус,
        "имя_блока": пасп.get("имя"),
        "архитектура": arch_имя,
        "чисел": arch_mod.чисел(obj) if obj and arch_mod else 0,
        "число_ответов": len(пасп.get("ответы", [])),
        "читает": пасп.get("читает", []),
        "пишет": пасп.get("пишет", []),
        "ошибки": ошибки,
        "предупреждения": предупреждения,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python NNL/линтер.py <папка_блока> [папка_архитектур]")
        sys.exit(1)

    папка = sys.argv[1]
    arch_dir = sys.argv[2] if len(sys.argv) > 2 else None
    res = проверить_блок(папка, arch_dir)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    sys.exit(0 if res["статус"] == "УСПЕХ" else 1)
