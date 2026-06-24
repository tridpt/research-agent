"""Currency and unit conversion tool.

Complements the calculator: converts physical units (deterministic, pure) and
currencies (live ECB rates via Frankfurter, no API key). Parsing and unit math
are pure functions; only ``fetch_currency`` performs network I/O.
"""
from __future__ import annotations

import re

FRANKFURTER_API = "https://api.frankfurter.dev/v1/latest"
USER_AGENT = "research-agent/0.1 (+https://github.com/tridpt/research-agent)"


class ConvertError(ValueError):
    """Raised when an expression cannot be parsed or units are unknown."""


# Length/mass/volume/time/data factors expressed in a common base unit per kind.
_UNIT_ALIASES = {
    "metre": "m", "meter": "m", "meters": "m", "metres": "m",
    "kilometre": "km", "kilometer": "km", "kilometers": "km", "kms": "km",
    "centimetre": "cm", "centimeter": "cm",
    "millimetre": "mm", "millimeter": "mm",
    "mile": "mi", "miles": "mi",
    "yard": "yd", "yards": "yd", "foot": "ft", "feet": "ft",
    "inch": "in", "inches": "in",
    "kilogram": "kg", "kilograms": "kg", "kilo": "kg", "kilos": "kg",
    "gram": "g", "grams": "g", "milligram": "mg",
    "pound": "lb", "pounds": "lb", "lbs": "lb",
    "ounce": "oz", "ounces": "oz",
    "tonne": "t", "tonnes": "t", "ton": "t",
    "litre": "l", "liter": "l", "litres": "l", "liters": "l",
    "millilitre": "ml", "milliliter": "ml",
    "gallon": "gal", "gallons": "gal",
    "second": "s", "seconds": "s", "sec": "s",
    "minute": "min", "minutes": "min", "mins": "min",
    "hour": "h", "hours": "h", "hr": "h", "hrs": "h",
    "day": "day", "days": "day",
    "celsius": "c", "fahrenheit": "f", "kelvin": "k",
    "kilobyte": "kb", "megabyte": "mb", "gigabyte": "gb", "terabyte": "tb",
}
_FACTORS: dict[str, tuple[str, float]] = {
    # unit -> (kind, factor to base)
    "m": ("length", 1.0), "km": ("length", 1000.0), "cm": ("length", 0.01),
    "mm": ("length", 0.001), "mi": ("length", 1609.344), "yd": ("length", 0.9144),
    "ft": ("length", 0.3048), "in": ("length", 0.0254),
    "kg": ("mass", 1.0), "g": ("mass", 0.001), "mg": ("mass", 1e-6),
    "lb": ("mass", 0.45359237), "oz": ("mass", 0.028349523125), "t": ("mass", 1000.0),
    "l": ("volume", 1.0), "ml": ("volume", 0.001), "gal": ("volume", 3.785411784),
    "s": ("time", 1.0), "min": ("time", 60.0), "h": ("time", 3600.0), "day": ("time", 86400.0),
    "kb": ("data", 1.0), "mb": ("data", 1000.0), "gb": ("data", 1e6), "tb": ("data", 1e9),
}
_TEMPERATURE = {"c", "f", "k"}
# A small set of common ISO-4217 currency codes the tool recognizes.
_CURRENCIES = {
    "usd", "eur", "gbp", "jpy", "cny", "vnd", "aud", "cad", "chf", "hkd", "sgd",
    "krw", "inr", "thb", "myr", "idr", "php", "rub", "brl", "zar", "sek", "nok",
    "dkk", "pln", "nzd", "mxn", "twd", "try", "aed",
}

_EXPR_RE = re.compile(
    r"^\s*([-+]?[\d.,]+)\s*([a-zA-Z°]+)\s*(?:to|in|->|=|as)\s*([a-zA-Z°]+)\s*$",
    re.IGNORECASE,
)


def _canonical_unit(raw: str) -> str:
    """Pure: lowercase + de-alias a unit token."""
    token = raw.strip().lower().rstrip(".").replace("°", "")
    return _UNIT_ALIASES.get(token, token)


def parse_conversion(text: str) -> tuple[float, str, str]:
    """Pure: parse 'AMOUNT FROM to TO' into (amount, from_unit, to_unit)."""
    match = _EXPR_RE.match(text or "")
    if not match:
        raise ConvertError("expected 'AMOUNT FROM to TO', e.g. '100 USD to EUR'")
    amount_raw, from_raw, to_raw = match.groups()
    # Tolerate thousands separators like '1,000'.
    amount_clean = amount_raw.replace(",", "")
    try:
        amount = float(amount_clean)
    except ValueError as exc:
        raise ConvertError(f"invalid amount: {amount_raw}") from exc
    return amount, _canonical_unit(from_raw), _canonical_unit(to_raw)


def is_currency(unit: str) -> bool:
    """Pure: True if ``unit`` is a recognized ISO currency code."""
    return unit.lower() in _CURRENCIES


def _convert_temperature(amount: float, from_u: str, to_u: str) -> float:
    celsius = {"c": amount, "f": (amount - 32) * 5 / 9, "k": amount - 273.15}[from_u]
    return {"c": celsius, "f": celsius * 9 / 5 + 32, "k": celsius + 273.15}[to_u]


def convert_units(amount: float, from_u: str, to_u: str) -> float:
    """Pure: convert between known physical units (raises if unknown/mismatched)."""
    if from_u in _TEMPERATURE and to_u in _TEMPERATURE:
        return _convert_temperature(amount, from_u, to_u)
    if from_u not in _FACTORS or to_u not in _FACTORS:
        raise ConvertError(f"unknown or unsupported units: {from_u} -> {to_u}")
    from_kind, from_factor = _FACTORS[from_u]
    to_kind, to_factor = _FACTORS[to_u]
    if from_kind != to_kind:
        raise ConvertError(f"cannot convert {from_kind} to {to_kind}")
    return amount * from_factor / to_factor


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def fetch_currency(amount: float, from_c: str, to_c: str, *, timeout: float = 15.0) -> float:
    """Convert currency via Frankfurter (live ECB rates). Network I/O isolated here."""
    import httpx

    params: dict[str, str | float] = {"amount": amount, "from": from_c.upper(), "to": to_c.upper()}
    try:
        resp = httpx.get(
            FRANKFURTER_API, params=params, timeout=timeout,
            headers={"User-Agent": USER_AGENT}, follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise ConvertError(f"could not fetch exchange rate: {exc}") from exc
    except ValueError as exc:  # pragma: no cover - invalid JSON
        raise ConvertError(f"invalid rate response: {exc}") from exc
    rates = data.get("rates") if isinstance(data, dict) else None
    if not isinstance(rates, dict) or to_c.upper() not in rates:
        raise ConvertError(f"no exchange rate for {from_c.upper()} -> {to_c.upper()}")
    return float(rates[to_c.upper()])


def convert(text: str) -> str:
    """Parse and evaluate a conversion; return a human-readable result string.

    Tries physical-unit conversion first (pure), then currency (live rates).
    """
    amount, from_u, to_u = parse_conversion(text)
    if is_currency(from_u) and is_currency(to_u):
        result = fetch_currency(amount, from_u, to_u)
        return f"{_format_number(amount)} {from_u.upper()} = {_format_number(result)} {to_u.upper()}"
    value = convert_units(amount, from_u, to_u)
    return f"{_format_number(amount)} {from_u} = {_format_number(value)} {to_u}"
