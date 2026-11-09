"""受限表达式求值器。

设计目标：让规则包能写公式，但**无法执行任意代码**。

白名单策略：
  - 只允许字面量、字段名、四则运算、括号、少量内置函数
  - 禁止属性访问、下标、函数定义、lambda、推导式、import
  - 解析用 Python 的 ast，校验后自行求值，不调用 eval/compile 执行
"""

from __future__ import annotations

import ast
import math
import operator
from typing import Any

MAX_DEPTH = 32
MAX_EXPR_LEN = 500

_ALLOWED_FUNCS = {
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
}

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_CMPOPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


class ExprError(Exception):
    pass


def _eval(node: ast.AST, env: dict[str, Any], depth: int = 0):
    if depth > MAX_DEPTH:
        raise ExprError("表达式嵌套过深")

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ExprError(f"不支持的字面量：{node.value!r}")

    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ExprError(f"未知字段：{node.id}")
        val = env[node.id]
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val
        try:
            return float(val)
        except Exception:
            raise ExprError(f"字段 {node.id} 不是数字")

    if isinstance(node, ast.Compare):
        left = _eval(node.left, env, depth + 1)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval(comparator, env, depth + 1)
            fn = _CMPOPS.get(type(op))
            if fn is None:
                raise ExprError("不支持的比较运算")
            if not fn(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        values = [_eval(v, env, depth + 1) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(bool(v) for v in values)
        if isinstance(node.op, ast.Or):
            return any(bool(v) for v in values)
        raise ExprError("不支持的布尔运算")

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not bool(_eval(node.operand, env, depth + 1))

    if isinstance(node, ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise ExprError("不支持的运算符")
        left = _eval(node.left, env, depth + 1)
        right = _eval(node.right, env, depth + 1)
        if isinstance(node.op, ast.Pow) and abs(right) > 32:
            raise ExprError("指数过大")
        try:
            return op(left, right)
        except ZeroDivisionError:
            raise ExprError("除零")

    if isinstance(node, ast.UnaryOp):
        op = _UNARYOPS.get(type(node.op))
        if op is None:
            raise ExprError("不支持的一元运算")
        return op(_eval(node.operand, env, depth + 1))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise ExprError("不支持的函数")
        if node.keywords:
            raise ExprError("不支持关键字参数")
        args = [_eval(a, env, depth + 1) for a in node.args]
        if len(args) > 8:
            raise ExprError("参数过多")
        try:
            return _ALLOWED_FUNCS[node.func.id](*args)
        except Exception as exc:
            raise ExprError(f"函数调用失败：{exc}")

    raise ExprError(f"不支持的语法：{type(node).__name__}")


def validate(expr: str) -> None:
    """只校验不执行，用于导入时检查。"""
    if not isinstance(expr, str):
        raise ExprError("表达式必须是字符串")
    if len(expr) > MAX_EXPR_LEN:
        raise ExprError("表达式过长")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExprError(f"语法错误：{exc.msg}") from exc
    _eval(tree.body, _Dummy, 0)


class _DummyDict(dict):
    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return 1


_Dummy = _DummyDict()


def evaluate(expr: str, env: dict[str, Any]):
    if not isinstance(expr, str):
        raise ExprError("表达式必须是字符串")
    if len(expr) > MAX_EXPR_LEN:
        raise ExprError("表达式过长")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExprError(f"语法错误：{exc.msg}") from exc
    return _eval(tree.body, env, 0)


def evaluate_bool(expr: str, env: dict[str, Any]) -> bool:
    return bool(evaluate(expr, env))


def lookup(table: list[dict], value: float):
    """区间表：按 max 升序匹配第一个 >= value 的项。"""
    for row in sorted(table, key=lambda r: float(r.get("max", 0))):
        try:
            if value <= float(row.get("max")):
                return row.get("value")
        except (TypeError, ValueError):
            continue
    return None


def to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(float(value))
