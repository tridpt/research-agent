"""Tests for the report style/length option (brief | standard | deep)."""
from __future__ import annotations

from research_agent.config import ENV_API_KEY, ENV_STYLE, resolve_settings
from research_agent.models import Source
from research_agent.synthesizer import style_instruction, synthesize

from .fakes import ScriptedLLM


def test_style_instruction_brief_and_deep_differ() -> None:
    assert "BRIEF" in style_instruction("brief")
    assert "IN-DEPTH" in style_instruction("deep")
    assert style_instruction("standard") == ""
    # Unknown / None falls back to no extra guidance.
    assert style_instruction(None) == ""
    assert style_instruction("nonsense") == ""


def test_style_instruction_is_case_insensitive() -> None:
    assert style_instruction("Brief") == style_instruction("brief")


def test_resolve_settings_reads_style_from_cli_and_env() -> None:
    cli = resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides={"report_style": "deep"})
    assert cli.report_style == "deep"

    env = resolve_settings(env={ENV_API_KEY: "k", ENV_STYLE: "brief"}, cli_overrides={})
    assert env.report_style == "brief"


def test_resolve_settings_defaults_and_rejects_invalid_style() -> None:
    default = resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides={})
    assert default.report_style == "standard"

    invalid = resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides={"report_style": "huge"})
    assert invalid.report_style == "standard"


class _CapturingLLM(ScriptedLLM):
    """Records the system prompt seen by the synthesizer."""

    def __init__(self) -> None:
        super().__init__(decisions=[], text="Answer [1]")
        self.system_prompt = ""

    def generate(self, messages):  # type: ignore[override]
        self.system_prompt = messages[0].content
        return super().generate(messages)


def test_synthesize_injects_style_guidance_into_prompt() -> None:
    llm = _CapturingLLM()
    sources = [Source(url="https://a.com", content="evidence " * 50, fetched_at=0.0)]
    synthesize("q", sources, llm, style="brief")
    assert "BRIEF" in llm.system_prompt
