"""Tests for the loadable domain-reputation configuration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_agent.source_quality import (
    apply_reputation,
    assess_source,
    configure_reputation_from_file,
    configure_reputation_from_mapping,
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
    established, low, weights = load_reputation_file(path)
    assert "good.example" in established  # normalized to lowercase
    assert "bad.example" in low
    assert weights == {}


def test_configure_reputation_from_file_applies(tmp_path: Path) -> None:
    path = tmp_path / "rep.json"
    path.write_text(json.dumps({"established": ["cool-lab.example"]}), encoding="utf-8")
    configure_reputation_from_file(path)
    assert "established" in assess_source("https://cool-lab.example/paper").reason


def test_load_reputation_file_missing_raises() -> None:
    with pytest.raises(ValueError):
        load_reputation_file("does-not-exist-12345.json")


# --------------------------------------------------------------------------
# Per-domain reputation weights
# --------------------------------------------------------------------------
def test_weights_boost_a_domain_score() -> None:
    baseline = assess_source("https://tuned-lab.example/paper").score
    apply_reputation(weights={"tuned-lab.example": 25})
    boosted = assess_source("https://tuned-lab.example/paper").score
    assert boosted == baseline + 25
    assert "reputation weight" in assess_source("https://tuned-lab.example/paper").reason


def test_weights_penalize_a_domain_score() -> None:
    baseline = assess_source("https://meh-site.example/post").score
    apply_reputation(weights={"meh-site.example": -20})
    lowered = assess_source("https://meh-site.example/post").score
    assert lowered == baseline - 20


def test_weights_apply_to_subdomains() -> None:
    apply_reputation(weights={"lab.example": 15})
    q = assess_source("https://blog.lab.example/post")
    assert "reputation weight" in q.reason


def test_weights_clamp_final_score_within_bounds() -> None:
    # A huge positive weight can't push the final score above 100.
    apply_reputation(weights={"cap.example": 100})
    assert assess_source("https://cap.example/x", "evidence " * 200).score == 100


def test_load_reputation_file_reads_weights(tmp_path: Path) -> None:
    path = tmp_path / "rep.json"
    path.write_text(
        json.dumps({"weights": {"A.Example": 10, "bad": "not-an-int", "": 5}}),
        encoding="utf-8",
    )
    _established, _low, weights = load_reputation_file(path)
    assert weights == {"a.example": 10}  # normalized, invalid/empty entries dropped


def test_configure_reputation_from_file_applies_weights(tmp_path: Path) -> None:
    path = tmp_path / "rep.json"
    path.write_text(json.dumps({"weights": {"weighted-lab.example": 30}}), encoding="utf-8")
    configure_reputation_from_file(path)
    assert "reputation weight" in assess_source("https://weighted-lab.example/x").reason


def test_weights_clamped_when_loaded(tmp_path: Path) -> None:
    path = tmp_path / "rep.json"
    path.write_text(json.dumps({"weights": {"x.example": 9999}}), encoding="utf-8")
    _e, _l, weights = load_reputation_file(path)
    assert weights["x.example"] == 100


# --------------------------------------------------------------------------
# Applying reputation from an already-parsed mapping (used by the Streamlit UI)
# --------------------------------------------------------------------------
def test_configure_reputation_from_mapping_applies_lists_and_weights() -> None:
    configure_reputation_from_mapping(
        {
            "established": ["ui-lab.example"],
            "low_evidence": ["ui-spam.example"],
            "weights": {"ui-boost.example": 20},
        }
    )
    assert "established" in assess_source("https://ui-lab.example/x").reason
    assert "social" in assess_source("https://ui-spam.example/x").reason

    base = assess_source("https://plain.example/x").score
    boosted = assess_source("https://ui-boost.example/x").score
    assert boosted == base + 20


def test_configure_reputation_from_mapping_rejects_non_dict() -> None:
    with pytest.raises(ValueError):
        configure_reputation_from_mapping(["not", "a", "dict"])
