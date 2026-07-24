"""Unit tests for the pure UI theme helpers."""
from __future__ import annotations

from ui.theme import THEME_CSS, hero_html


def test_theme_css_is_non_empty_and_scoped() -> None:
    assert isinstance(THEME_CSS, str) and THEME_CSS.strip()
    # Uses the brand CSS variables and styles the primary button + tabs.
    assert "--ra-primary" in THEME_CSS
    assert ".stButton" in THEME_CSS
    assert ".stTabs" in THEME_CSS


def test_hero_html_embeds_copy_and_chips() -> None:
    html = hero_html(
        title="🔎 Research Agent",
        subtitle="does research",
        badge="AI Research Assistant",
        chips=["🔍 Web search", "🔖 Cited report"],
    )
    assert "ra-hero" in html
    assert "AI Research Assistant" in html
    assert "🔍 Web search" in html
    assert "🔖 Cited report" in html
    # Every chip is wrapped in a chip span.
    assert html.count("ra-chip") == 2
