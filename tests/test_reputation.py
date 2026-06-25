"""Tests for the loadable domain-reputation configuration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_agent.source_quality import (
    apply_reputation,
    assess_source,
    configure_reputation_from_file,
    load_reputation_file,
    reset_reputation,
)


@pytest.fixture(autouse=True)
def _restore_reputation():
    """Keep the global reputation lists isolated per test."""
    yield
    reset_reputation()


def test_apply_reputation_promotes_a_custom_established_domain() -> None:
    before = assess_source("https://my-trusted-journal.example/article")
    assert "established" not in before.reason

    apply_reputation(established={"my-trusted-journal.example"})
    after = assess_source("https://my-trusted-journal.example/article")
    assert "established or reputable source" in after.reason
    assert after.score > before.score


def test_apply_reputation_demotes_a_custom_low_evidence_domain() -> None:
    apply_reputation(low_evidence={"spammy-forum.example"})
    quality = assess_source("https://spammy-forum.example/thread")
    assert "social or user-generated platform" in quality.reason


def test_apply_reputation_keeps_builtin_defaults() -> None:
    apply_reputation(established={"extra.example"})
    # A built-in established host is still recognized.
    assert "established" in assess_source("https://www.reuters.com/x").reason


def test_load_reputation_file_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "rep.json"
    path.write_text(
        json.dumps({"established": ["Good.Example"], "low_evidence": ["Bad.Example"]}),
        encoding="utf-8",
    )
    established, low = load_reputation_file(path)
    assert "good.example" in established  # normalized to lowercase
    assert "bad.example" in low


def test_configure_reputation_from_file_applies(tmp_path: Path) -> None:
    path = tmp_path / "rep.json"
    path.write_text(json.dumps({"established": ["cool-lab.example"]}), encoding="utf-8")
    configure_reputation_from_file(path)
    assert "established" in assess_source("https://cool-lab.example/paper").reason


def test_load_reputation_file_missing_raises() -> None:
    with pytest.raises(ValueError):
        load_reputation_file("does-not-exist-12345.json")
