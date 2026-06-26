"""Tests for direct PDF export (pure parsing always; rendering when available)."""
from __future__ import annotations

import importlib.util

import pytest

from research_agent.pdf_export import (
    PdfBlock,
    find_unicode_font,
    markdown_to_blocks,
    render_pdf_bytes,
    strip_inline_markdown,
)

_HAS_FPDF = importlib.util.find_spec("fpdf") is not None
_HAS_FONT = find_unicode_font() is not None


def test_strip_inline_markdown_removes_syntax_keeps_text() -> None:
    assert strip_inline_markdown("**bold** and _italic_ and `code`") == "bold and italic and code"


def test_strip_inline_markdown_keeps_link_text() -> None:
    out = strip_inline_markdown("see [the docs](https://example.com/x)")
    assert "the docs" in out
    # The URL is no longer inlined into the text (it becomes the block's link).
    assert "(https://example.com/x)" not in out


def test_extract_link_finds_markdown_and_bare_urls() -> None:
    from research_agent.pdf_export import extract_link

    assert extract_link("see [docs](https://example.com/x)") == "https://example.com/x"
    assert extract_link("1. https://a.gov/report — Quality: high") == "https://a.gov/report"
    assert extract_link("no link here") is None


def test_markdown_to_blocks_attaches_link_to_source_lines() -> None:
    blocks = markdown_to_blocks("## Sources\n\n1. [https://a.gov/x](https://a.gov/x) — Quality: high")
    source_block = blocks[-1]
    assert source_block.kind == "bullet"
    assert source_block.link == "https://a.gov/x"


def test_markdown_to_blocks_classifies_lines() -> None:
    md = "# Title\n\nIntro paragraph.\n\n## Section\n\n- first\n- second\n\n1. one\n2. two"
    blocks = markdown_to_blocks(md)
    kinds = [b.kind for b in blocks]
    assert kinds[0] == "h1"
    assert "h2" in kinds
    assert kinds.count("bullet") == 4
    assert PdfBlock("para", "Intro paragraph.") in blocks


def test_markdown_to_blocks_treats_code_fence_as_paragraphs() -> None:
    md = "```\ncode line\n```\nafter"
    blocks = markdown_to_blocks(md)
    texts = [b.text for b in blocks]
    assert "code line" in texts
    assert "after" in texts


@pytest.mark.skipif(not (_HAS_FPDF and _HAS_FONT), reason="fpdf2 and a Unicode font are required")
def test_render_pdf_bytes_produces_valid_pdf() -> None:
    data = render_pdf_bytes("Báo cáo thử nghiệm", "# Tiêu đề\n\nNội dung tiếng Việt có dấu.\n\n- mục một")
    assert data.startswith(b"%PDF-")
    assert len(data) > 500
