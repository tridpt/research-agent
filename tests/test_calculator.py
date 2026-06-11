"""Tests for the safe calculator tool."""
from __future__ import annotations

import pytest

from research_agent.calculator import CalculatorError, calculate, calculate_str, now_str


def test_basic_arithmetic() -> None:
    assert calculate("1 + 2 * 3") == 7.0
    assert calculate("(120 - 90) / 90 * 100") == pytest.approx(33.333, rel=1e-3)
    assert calculate("2 ** 10") == 1024.0
    assert calculate("-5 + 3") == -2.0


def test_calculate_str_formats_ints() -> None:
    assert calculate_str("4 * 5") == "20"
    assert calculate_str("10 / 4") == "2.5"


def test_division_by_zero() -> None:
    with pytest.raises(CalculatorError):
        calculate("1 / 0")


def test_empty_expression() -> None:
    with pytest.raises(CalculatorError):
        calculate("   ")


def test_rejects_names_and_calls() -> None:
    # No arbitrary code execution: names, calls, attributes are disallowed.
    for expr in ["__import__('os')", "abs(-1)", "x + 1", "().__class__"]:
        with pytest.raises(CalculatorError):
            calculate(expr)


def test_rejects_huge_exponent() -> None:
    with pytest.raises(CalculatorError):
        calculate("2 ** 100000")


def test_now_str_uses_clock() -> None:
    # Fixed timestamp -> deterministic formatted string.
    fixed = 1_700_000_000.0  # 2023-11-14 ~UTC
    out = now_str(lambda: fixed)
    assert out.startswith("2023-11-14") or out.startswith("2023-11-15")  # tz-dependent
