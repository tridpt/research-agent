"""Stock-quote tool helpers.

Fetches the latest quote from Yahoo Finance's public chart endpoint, which
needs no API key (mirroring how the weather tool uses wttr.in). Parsing and
formatting are pure functions so they can be unit-tested without any network,
while the single HTTP call lives behind ``fetch_stock_quote``.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any

# Free, key-less quote endpoint. ``{symbol}`` is the ticker (e.g. AAPL, ^GSPC,
# BTC-USD, EURUSD=X).
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"


class StockError(ValueError):
    """Raised when a symbol is invalid or no quote could be parsed."""


@dataclass(frozen=True)
class StockQuote:
    symbol: str
    price: float
    currency: str = ""
    day_high: float | None = None
    day_low: float | None = None
    previous_close: float | None = None
    volume: float | None = None
    market_time: str = ""
    exchange: str = ""


def normalize_symbol(raw: str) -> str:
    """Pure: clean a user-supplied ticker for the quote query.

    Trims whitespace and drops characters Yahoo tickers never use, so untrusted
    model output cannot inject path/query parameters.
    """
    cleaned = (raw or "").strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.^-=")
    cleaned = "".join(ch for ch in cleaned if ch in allowed)
    if not cleaned:
        raise StockError("empty stock symbol")
    return cleaned


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_yahoo_chart(payload: Any) -> StockQuote:
    """Pure: parse a Yahoo Finance chart response into a StockQuote.

    Raises StockError when the payload is malformed or reports an error (e.g.
    an unknown ticker), so callers never surface a half-empty quote.
    """
    if not isinstance(payload, dict):
        raise StockError("malformed response")
    chart = payload.get("chart")
    if not isinstance(chart, dict):
        raise StockError("malformed response")
    if chart.get("error"):
        raise StockError("symbol not found or no data available")
    results = chart.get("result")
    if not isinstance(results, list) or not results:
        raise StockError("symbol not found or no data available")
    meta = results[0].get("meta") if isinstance(results[0], dict) else None
    if not isinstance(meta, dict):
        raise StockError("no quote metadata in response")

    price = _to_float(meta.get("regularMarketPrice"))
    symbol = str(meta.get("symbol") or "").upper()
    if price is None or not symbol:
        raise StockError("symbol not found or no data available")

    market_time = ""
    epoch = _to_float(meta.get("regularMarketTime"))
    if epoch:
        market_time = _dt.datetime.fromtimestamp(epoch, tz=_dt.UTC).strftime(
            "%Y-%m-%d %H:%M UTC"
        )

    return StockQuote(
        symbol=symbol,
        price=price,
        currency=str(meta.get("currency") or ""),
        day_high=_to_float(meta.get("regularMarketDayHigh")),
        day_low=_to_float(meta.get("regularMarketDayLow")),
        previous_close=_to_float(meta.get("previousClose") or meta.get("chartPreviousClose")),
        volume=_to_float(meta.get("regularMarketVolume")),
        market_time=market_time,
        exchange=str(meta.get("exchangeName") or ""),
    )


def format_stock_quote(quote: StockQuote) -> str:
    """Pure: a compact, human-readable one-line summary of a quote."""
    price = f"{quote.price} {quote.currency}".strip()
    parts = [f"{quote.symbol}: {price}"]
    if quote.day_high is not None and quote.day_low is not None:
        parts.append(f"day range {quote.day_low}-{quote.day_high}")
    if quote.previous_close is not None:
        parts.append(f"prev close {quote.previous_close}")
    if quote.volume is not None:
        parts.append(f"volume {quote.volume:.0f}")
    if quote.exchange:
        parts.append(f"on {quote.exchange}")
    if quote.market_time:
        parts.append(f"as of {quote.market_time}")
    return ", ".join(parts)


def stock_quote_url(symbol: str) -> str:
    """Pure: the quote URL for a (already-normalized) symbol."""
    return YAHOO_URL.format(symbol=symbol)


def fetch_stock_quote(symbol: str, *, timeout: float = 10.0) -> tuple[str, str]:
    """Fetch a quote; return (source_url, human-readable summary).

    Network I/O is isolated here so the parser/formatter stay pure. Raises
    StockError on any network or parsing failure.
    """
    import httpx

    normalized = normalize_symbol(symbol)
    url = stock_quote_url(normalized)
    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; research-agent/0.1)"},
        )
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise StockError(f"could not fetch quote: {exc}") from exc
    except ValueError as exc:  # pragma: no cover - invalid JSON
        raise StockError(f"invalid quote response: {exc}") from exc
    quote = parse_yahoo_chart(payload)
    # The displayed source is the human-facing Yahoo Finance quote page.
    page_url = f"https://finance.yahoo.com/quote/{normalized}"
    return page_url, format_stock_quote(quote)
