"""Tests for the bilingual UI string helper."""
from __future__ import annotations

from ui.i18n import TRANSLATIONS, t


def test_t_returns_language_specific_string() -> None:
    assert t("vi", "run_btn") == "🚀 Bắt đầu nghiên cứu"
    assert t("en", "run_btn") == "🚀 Start research"


def test_t_falls_back_to_key_when_missing() -> None:
    assert t("en", "no_such_key_123") == "no_such_key_123"


def test_t_falls_back_to_vietnamese_for_unknown_lang() -> None:
    assert t("fr", "run_btn") == TRANSLATIONS["run_btn"]["vi"]


def test_t_formats_placeholders() -> None:
    out = t("en", "stats_line", elapsed=1.23, n=3, mode="Normal")
    assert "1.2s" in out
    assert "Sources: 3" in out
    assert "Normal" in out


def test_every_translation_has_both_languages() -> None:
    for key, entry in TRANSLATIONS.items():
        assert "vi" in entry and "en" in entry, f"missing language for {key}"
