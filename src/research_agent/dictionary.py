"""Dictionary lookup tool (free dictionaryapi.dev, no key).

Returns definitions and part-of-speech for an English word. Parsing/formatting
are pure; only ``fetch_definition`` performs network I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DICT_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
USER_AGENT = "research-agent/0.1 (+https://github.com/tridpt/research-agent)"


class DictionaryError(ValueError):
    """Raised when a word is invalid or no definition could be parsed."""


@dataclass(frozen=True)
class Definition:
    part_of_speech: str
    text: str


@dataclass(frozen=True)
class DictionaryEntry:
    word: str
    phonetic: str
    definitions: tuple[Definition, ...]


def normalize_word(raw: str) -> str:
    """Pure: a single clean word (letters/hyphen/apostrophe); reject empty."""
    cleaned = "".join(c for c in (raw or "").strip().lower() if c.isalpha() or c in "-'")
    if not cleaned:
        raise DictionaryError("empty word")
    return cleaned


def parse_dictionary(payload: Any, max_definitions: int = 6) -> DictionaryEntry:
    """Pure: parse a dictionaryapi.dev response into a DictionaryEntry."""
    if not isinstance(payload, list) or not payload:
        raise DictionaryError("word not found")
    first = payload[0]
    if not isinstance(first, dict):
        raise DictionaryError("malformed response")
    word = str(first.get("word") or "").strip()
    phonetic = str(first.get("phonetic") or "").strip()
    definitions: list[Definition] = []
    for meaning in first.get("meanings", []) or []:
        if not isinstance(meaning, dict):
            continue
        pos = str(meaning.get("partOfSpeech") or "").strip()
        for d in meaning.get("definitions", []) or []:
            if isinstance(d, dict) and str(d.get("definition") or "").strip():
                definitions.append(Definition(pos, str(d["definition"]).strip()))
            if len(definitions) >= max_definitions:
                break
        if len(definitions) >= max_definitions:
            break
    if not word or not definitions:
        raise DictionaryError("no usable definition")
    return DictionaryEntry(word=word, phonetic=phonetic, definitions=tuple(definitions))


def format_entry(entry: DictionaryEntry) -> str:
    """Pure: a readable plain-text block for the entry."""
    head = f"Dictionary — {entry.word}" + (f" {entry.phonetic}" if entry.phonetic else "")
    lines = [head]
    for i, d in enumerate(entry.definitions, start=1):
        pos = f"({d.part_of_speech}) " if d.part_of_speech else ""
        lines.append(f"{i}. {pos}{d.text}")
    return "\n".join(lines)


def fetch_definition(word: str, *, timeout: float = 15.0) -> tuple[str, str]:
    """Fetch a definition; return (source_url, formatted content)."""
    import httpx

    clean = normalize_word(word)
    try:
        resp = httpx.get(
            DICT_API.format(word=clean), timeout=timeout,
            headers={"User-Agent": USER_AGENT}, follow_redirects=True,
        )
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise DictionaryError(f"could not fetch definition: {exc}") from exc
    except ValueError as exc:  # pragma: no cover - invalid JSON
        raise DictionaryError(f"invalid definition response: {exc}") from exc
    entry = parse_dictionary(payload)
    return f"https://en.wiktionary.org/wiki/{clean}", format_entry(entry)
