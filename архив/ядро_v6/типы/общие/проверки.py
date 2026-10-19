# -*- coding: utf-8 -*-
"""Проверки набора «общие», которые схемой не выразить. Код набора типов, не ядра и не блока; обученных чисел нет.

проверить_Ответ:
  - «выбор» обязан иметь id, «текст» — поле текст;
  - в тексте каждое вычисление, записанное как <<выражение=результат>> (запись калькулятора из GSM8K),
    пересчитывается обычной арифметикой (+ − × ÷ скобки). Неверный шаг — замечание, и ядро вместо ответа скажет «не знаю».
"""
import ast
import re

_CALC = re.compile(r"<<([^<>=]*)=([^<>]*)>>")
_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


def _num(s):
    return float(s.replace(" ", "").replace(",", ""))


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and isinstance(node.op, _OPS):
        a, b = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        return a / b
    raise ValueError("не арифметика")


def calc(expr):
    """Значение арифметического выражения или None, если это не арифметика."""
    try:
        return _eval(ast.parse(expr.replace(" ", "").replace(",", "").replace("×", "*").replace("÷", "/"), mode="eval"))
    except Exception:  # noqa: BLE001
        return None


def steps(text):
    """[(выражение, записанный результат, верно ли)] по всем <<…=…>> в тексте."""
    out = []
    for expr, res in _CALC.findall(text):
        v = calc(expr)
        try:
            r = _num(res)
        except ValueError:
            r = None
        ok = v is not None and r is not None and abs(v - r) <= 1e-6 * max(1.0, abs(v))
        out.append((expr, res, ok))
    return out


def проверить_Ответ(v):
    errs = []
    if v.get("вид") == "выбор" and "id" not in v:
        errs.append("выбор без id")
    if v.get("вид") == "текст":
        if "текст" not in v:
            errs.append("текст без поля текст")
        else:
            bad = [("%s=%s" % (e, r)) for e, r, ok in steps(v["текст"]) if not ok]
            if bad:
                errs.append("неверно посчитаны шаги: %s" % bad[:3])
    return errs
