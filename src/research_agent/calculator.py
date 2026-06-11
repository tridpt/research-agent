"""Safe arithmetic evaluator for the calculator tool.

Evaluates a basic math expression using Python's AST with a strict allow-list
of node types and operators. It never uses ``eval`` and never touches names,
calls, attributes, or comprehensions, so untrusted model output cannot run
arbitrary code.
"""
from __future__ import annotations

import ast
import operator
from collections.abc import Callable

_BIN_OPS: dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type, Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Guard against absurd exponents that could hang the process.
_MAX_POW_EXPONENT = 1000


class CalculatorError(ValueError):
    """Raised when an expression is invalid or uses disallowed operations."""


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError("only numeric literals are allowed")
        return float(node.value)
    if isinstance(node, ast.BinOp):
        bin_op = _BIN_OPS.get(type(node.op))
        if bin_op is None:
            raise CalculatorError(f"operator not allowed: {type(node.op).__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_POW_EXPONENT:
            raise CalculatorError("exponent too large")
        return bin_op(left, right)
    if isinstance(node, ast.UnaryOp):
        unary_op = _UNARY_OPS.get(type(node.op))
        if unary_op is None:
            raise CalculatorError(f"unary operator not allowed: {type(node.op).__name__}")
        return unary_op(_eval_node(node.operand))
    raise CalculatorError(f"expression element not allowed: {type(node).__name__}")


def calculate(expression: str) -> float:
    """Safely evaluate an arithmetic expression and return a float.

    Raises CalculatorError for empty, malformed, or disallowed expressions.
    """
    if not expression or not expression.strip():
        raise CalculatorError("empty expression")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"invalid expression: {exc}") from exc
    try:
        return _eval_node(tree.body)
    except ZeroDivisionError as exc:
        raise CalculatorError("division by zero") from exc


def calculate_str(expression: str) -> str:
    """Evaluate and format a result for inclusion in agent context."""
    result = calculate(expression)
    # Show integers without a trailing .0 for readability.
    if result == int(result):
        return str(int(result))
    return repr(result)


def now_str(clock: Callable[[], float] | None = None) -> str:
    """Return the current local date/time as an ISO-like string."""
    import datetime as _dt

    ts = clock() if clock else _dt.datetime.now().timestamp()
    return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
