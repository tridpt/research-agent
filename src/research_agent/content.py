"""Pure boundary helpers for handling web content.

These functions are deterministic and perform no I/O, making them the primary
targets for property-based testing (Properties 2 and 3) and the prompt-injection
isolation strategy (Property 4).
"""
from __future__ import annotations

from urllib.parse import urlsplit

# An unpredictable sentinel that brackets untrusted source text. The agent's
# system prompt instructs the model that anything between these markers is
# reference DATA, never instructions.
UNTRUSTED_OPEN = "<<<UNTRUSTED_SOURCE_DATA_3f9a1c>>>"
UNTRUSTED_CLOSE = "<<<END_UNTRUSTED_SOURCE_DATA_3f9a1c>>>"


def truncate_content(text: str, max_chars: int) -> str:
    """Return a prefix of ``text`` no longer than ``max_chars`` characters.

    If ``text`` is already within the limit it is returned unchanged.
    ``max_chars`` is clamped at 0 (negative limits yield an empty string).
    """
    if max_chars < 0:
        max_chars = 0
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _host_of(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.lower().rstrip(".")


def host_of(url: str) -> str:
    """Public: the lowercased host of a URL (used for source-diversity logic)."""
    return _host_of(url)


def is_blocked(url: str, blocked_domains: frozenset[str]) -> bool:
    """True iff the URL host equals, or is a subdomain of, a blocked domain."""
    if not blocked_domains:
        return False
    host = _host_of(url)
    if not host:
        return False
    for raw in blocked_domains:
        domain = raw.lower().strip().rstrip(".")
        if not domain:
            continue
        if host == domain or host.endswith("." + domain):
            return True
    return False


def wrap_untrusted(source_text: str) -> str:
    """Bracket untrusted source text inside an explicit data boundary.

    Any occurrence of the sentinel markers inside the source content is
    neutralised first, so a malicious page cannot "break out" of the data
    region and inject instructions.
    """
    cleaned = source_text.replace(UNTRUSTED_OPEN, "").replace(UNTRUSTED_CLOSE, "")
    return f"{UNTRUSTED_OPEN}\n{cleaned}\n{UNTRUSTED_CLOSE}"
