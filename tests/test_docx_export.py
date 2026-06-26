"""Tests for direct DOCX export (rendering when python-docx is available)."""
from __future__ import annotations

import importlib.util
import zipfile
from io import BytesIO

import pytest

from research_agent.docx_export import render_docx_bytes

_HAS_DOCX = importlib.util.find_spec("docx") is not None


@pytest.mark.skipif(not _HAS_DOCX, reason="python-docx is required")
def test_render_docx_bytes_produces_valid_docx() -> None:
    md = "# Tiêu đề\n\nNội dung tiếng Việt có dấu.\n\n## Mục\n\n- một\n- hai"
    data = render_docx_bytes("Báo cáo thử nghiệm", md)
    # A .docx is a ZIP container holding the Word XML parts.
    assert data[:2] == b"PK"
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        assert "word/document.xml" in names
        body = zf.read("word/document.xml").decode("utf-8")
    # Vietnamese content survives round-trip into the document body.
    assert "Nội dung tiếng Việt" in body


@pytest.mark.skipif(_HAS_DOCX, reason="covers the missing-dependency path")
def test_render_docx_bytes_raises_without_python_docx() -> None:
    from research_agent.docx_export import DocxExportError

    with pytest.raises(DocxExportError):
        render_docx_bytes("t", "# x")


@pytest.mark.skipif(not _HAS_DOCX, reason="python-docx is required")
def test_render_docx_bytes_makes_sources_clickable() -> None:
    md = "## Sources\n\n1. [https://a.gov/report](https://a.gov/report) — Quality: high"
    data = render_docx_bytes("Report", md)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        document = zf.read("word/document.xml").decode("utf-8")
        rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
    # A hyperlink element references the external source URL.
    assert "hyperlink" in document.lower()
    assert "https://a.gov/report" in rels
