"""Tests for the convert tool: parsing and pure unit conversion."""
from __future__ import annotations

import pytest

from research_agent.convert import (
    ConvertError,
    convert_units,
    is_currency,
    parse_conversion,
)
from research_agent.decision import parse_decision
from research_agent.models import ActionType, AgentDecision
from research_agent.tools import TOOL_SCHEMAS


def test_parse_conversion_basic_and_aliases() -> None:
    assert parse_conversion("100 USD to EUR") == (100.0, "usd", "eur")
    assert parse_conversion("10 kilometers in miles") == (10.0, "km", "mi")
    assert parse_conversion("1,000 g = kg") == (1000.0, "g", "kg")


def test_parse_conversion_rejects_garbage() -> None:
    with pytest.raises(ConvertError):
        parse_conversion("convert some stuff")


def test_convert_units_length_and_mass() -> None:
    assert convert_units(1.0, "km", "m") == 1000.0
    assert round(convert_units(1.0, "mi", "km"), 3) == 1.609
    assert round(convert_units(1.0, "lb", "g"), 2) == 453.59


def test_convert_units_temperature() -> None:
    assert convert_units(0.0, "c", "f") == 32.0
    assert convert_units(100.0, "c", "k") == 373.15
    assert round(convert_units(32.0, "f", "c"), 2) == 0.0


def test_convert_units_mismatched_kind_raises() -> None:
    with pytest.raises(ConvertError):
        convert_units(1.0, "km", "kg")


def test_convert_units_unknown_unit_raises() -> None:
    with pytest.raises(ConvertError):
        convert_units(1.0, "foo", "bar")


def test_is_currency() -> None:
    assert is_currency("usd") is True
    assert is_currency("EUR") is True
    assert is_currency("km") is False


def test_parse_decision_accepts_convert() -> None:
    decision = parse_decision({"action": "convert", "expression": "100 USD to EUR"})
    assert isinstance(decision, AgentDecision)
    assert decision.action is ActionType.CONVERT
    assert decision.conversion == "100 USD to EUR"


def test_parse_decision_rejects_convert_without_expression() -> None:
    assert not isinstance(parse_decision({"action": "convert"}), AgentDecision)


def test_convert_tool_is_advertised() -> None:
    assert "convert" in {t["function"]["name"] for t in TOOL_SCHEMAS}
