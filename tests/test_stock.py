"""Tests for the stock-quote tool: parsing, formatting, and wiring."""
from __future__ import annotations

import pytest

from research_agent.decision import parse_decision
from research_agent.models import ActionType, AgentDecision
from research_agent.stock import (
    StockError,
    format_stock_quote,
    normalize_symbol,
    parse_yahoo_chart,
    stock_quote_url,
)
from research_agent.tools import TOOL_SCHEMAS


def _chart(meta: dict) -> dict:
    return {"chart": {"result": [{"meta": meta}], "error": None}}


_GOOD_META = {
    "symbol": "AAPL",
    "regularMarketPrice": 207.49,
    "currency": "USD",
    "regularMarketDayHigh": 211.89,
    "regularMarketDayLow": 207.11,
    "previousClose": 209.07,
    "regularMarketVolume": 79665230,
    "regularMarketTime": 1719007209,
    "exchangeName": "NMS",
}


def test_normalize_symbol_cleans_whitespace_and_keeps_ticker_chars() -> None:
    assert normalize_symbol("  AAPL ") == "AAPL"
    assert normalize_symbol("^GSPC") == "^GSPC"
    assert normalize_symbol("BTC-USD") == "BTC-USD"
    assert normalize_symbol("EURUSD=X") == "EURUSD=X"
    # Strips characters that could inject path/query params.
    assert normalize_symbol("AAPL/../x?y=1") == "AAPL..xy=1"


def test_normalize_symbol_rejects_empty() -> None:
    with pytest.raises(StockError):
        normalize_symbol("   ")


def test_parse_yahoo_chart_valid() -> None:
    quote = parse_yahoo_chart(_chart(_GOOD_META))
    assert quote.symbol == "AAPL"
    assert quote.price == 207.49
    assert quote.day_high == 211.89
    assert quote.previous_close == 209.07
    assert quote.volume == 79665230
    assert "UTC" in quote.market_time


def test_parse_yahoo_chart_error_field_raises() -> None:
    with pytest.raises(StockError):
        parse_yahoo_chart({"chart": {"result": None, "error": {"code": "Not Found"}}})


def test_parse_yahoo_chart_missing_price_raises() -> None:
    with pytest.raises(StockError):
        parse_yahoo_chart(_chart({"symbol": "X"}))


def test_parse_yahoo_chart_malformed_raises() -> None:
    with pytest.raises(StockError):
        parse_yahoo_chart("not a dict")


def test_format_stock_quote_is_compact_and_informative() -> None:
    summary = format_stock_quote(parse_yahoo_chart(_chart(_GOOD_META)))
    assert "AAPL" in summary
    assert "207.49 USD" in summary
    assert "day range 207.11-211.89" in summary
    assert "as of" in summary


def test_stock_quote_url_uses_symbol() -> None:
    assert "AAPL" in stock_quote_url("AAPL")
    assert stock_quote_url("AAPL").startswith("https://")


def test_parse_decision_accepts_get_stock() -> None:
    decision = parse_decision({"action": "get_stock", "symbol": "AAPL", "reasoning": "price"})
    assert isinstance(decision, AgentDecision)
    assert decision.action is ActionType.GET_STOCK
    assert decision.symbol == "AAPL"


def test_parse_decision_rejects_get_stock_without_symbol() -> None:
    decision = parse_decision({"action": "get_stock"})
    assert not isinstance(decision, AgentDecision)


def test_get_stock_tool_is_advertised() -> None:
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert "get_stock" in names
