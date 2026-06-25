"""Weather lookup tool.

Fetches current conditions from wttr.in (no API key). The network call is
isolated here so the agent dispatch stays uniform across info tools.
"""
from __future__ import annotations

from urllib.parse import quote


class WeatherError(ValueError):
    """Raised when weather data cannot be fetched."""


def fetch_weather(location: str, *, timeout: float = 10.0) -> tuple[str, str]:
    """Fetch current weather; return (source_url, human-readable summary).

    Raises WeatherError on any network failure.
    """
    import httpx

    loc = (location or "").strip()
    url = f"https://wttr.in/{quote(loc, safe='')}?format=3"
    try:
        resp = httpx.get(url, timeout=timeout, headers={"User-Agent": "research-agent/0.1"})
        resp.raise_for_status()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise WeatherError(f"could not fetch weather: {exc}") from exc
    return url, f"Weather for '{loc}': {resp.text.strip()}"
