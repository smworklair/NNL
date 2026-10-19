# -*- coding: utf-8 -*-
"""Числа как символы — код блока-решателя (обученных чисел нет).
Вопрос: каждое число заменяется символом N1, N2, … (одинаковые значения — один символ).
Решение: вычисление пишется как <<N1*N2=R1>>, где R1 — результат (его считает код), дальше в тексте — символы.
Сеть решает, ЧТО с чем делать; переписывать и считать цифры ей не нужно.
Перевод готового решения (формат GSM8K: <<48/2=24>>24) в символы делается здесь же — для обучения."""
import re

NUM = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)(?![\w])")
SYM = re.compile(r"\b([NR])(\d+)\b")
CALC = re.compile(r"<<([^<>=]*)=([^<>]*)>>")
MAX_SYM = 20


def value(s):
    return float(s.replace(",", "."))


def fmt(v):
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else ("%.4f" % v).rstrip("0").rstrip(".")


def question_to_symbols(q):
    """(вопрос с символами, {символ: значение})."""
    vals, out, pos = {}, [], 0
    for m in NUM.finditer(q):
        v = value(m.group(1))
        sym = next((s for s, x in vals.items() if abs(x - v) < 1e-9), None)
        if sym is None:
            if len(vals) >= MAX_SYM:
                continue
            sym = "N%d" % (len(vals) + 1)
            vals[sym] = v
        out.append(q[pos:m.start()])
        out.append(sym)
        pos = m.end()
    out.append(q[pos:])
    return "".join(out), vals


def answer_to_symbols(ans, qvals):
    """Решение GSM8K → символьное. None, если не удалось (например, слишком много результатов)."""
    res = {}

    def sym_of(v):
        for s, x in list(qvals.items()):
            if abs(x - v) < 1e-9:
                return s
        for s, x in sorted(res.items(), key=lambda t: -int(t[0][1:])):
            if abs(x - v) < 1e-9:
                return s
        return None

    def sub_numbers(text):
        def rep(m):
            s = sym_of(value(m.group(1)))
            return s if s else m.group(1)
        return NUM.sub(rep, text)

    out, pos = [], 0
    for m in CALC.finditer(ans):
        out.append(sub_numbers(ans[pos:m.start()]))
        expr, r = m.group(1), m.group(2)
        try:
            rv = value(r.strip())
        except ValueError:
            return None
        if len(res) >= MAX_SYM:
            return None
        rs = "R%d" % (len(res) + 1)
        out.append("<<" + sub_numbers(expr) + "=" + rs + ">>")
        res[rs] = rv
        pos = m.end()
        # повтор результата сразу после >> (как «>>24») → тот же символ
        mm = re.match(r"\s?(\d+(?:[.,]\d+)?)", ans[pos:])
        if mm and abs(value(mm.group(1)) - rv) < 1e-9:
            out.append(ans[pos:pos + mm.start(1)] + rs)
            pos += mm.end()
    out.append(sub_numbers(ans[pos:]))
    return "".join(out)


def eval_expr(expr, env):
    """Значение выражения над символами и числами или None."""
    import ast
    e = SYM.sub(lambda m: "(%s)" % fmt(env[m.group(0)]) if m.group(0) in env else "None", expr).replace(",", ".").replace(" ", "")
    if "None" in e:
        return None
    try:
        node = ast.parse(e, mode="eval")
    except SyntaxError:
        return None

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = ev(n.left), ev(n.right)
            return a + b if isinstance(n.op, ast.Add) else a - b if isinstance(n.op, ast.Sub) else a * b if isinstance(n.op, ast.Mult) else a / b
        raise ValueError
    try:
        return ev(node)
    except (ValueError, ZeroDivisionError):
        return None


def render(text, env):
    """Символы → значения. Вычисление <<N1*N2=R1>> → <<5*3=15>>15 (как в GSM8K, для человека и проверки типа)."""
    def calc_rep(m):
        expr, rs = m.group(1), m.group(2).strip()
        e = SYM.sub(lambda mm: fmt(env[mm.group(0)]) if mm.group(0) in env else mm.group(0), expr)
        r = fmt(env[rs]) if rs in env else rs
        return "<<%s=%s>>" % (e, r)
    t = CALC.sub(calc_rep, text)
    return SYM.sub(lambda m: fmt(env[m.group(0)]) if m.group(0) in env else m.group(0), t)
