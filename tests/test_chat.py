"""Tests for the CLI follow-up chat loop."""
from __future__ import annotations

from research_agent.chat import build_chat_messages, is_quit, run_chat_loop

from .fakes import ScriptedLLM


def test_build_chat_messages_grounds_on_report_and_history() -> None:
    messages = build_chat_messages(
        "REPORT BODY",
        history=[("user", "q1"), ("assistant", "a1")],
        follow_up="q2",
        language="vi",
    )
    assert messages[0].role == "system"
    assert "tiếng Việt" in messages[0].content
    assert "REPORT BODY" in messages[1].content
    assert messages[-1].content == "q2"
    # Prior turns are preserved between report context and the new question.
    assert [m.role for m in messages] == ["system", "user", "user", "assistant", "user"]


def test_is_quit() -> None:
    for q in ("", "  ", "quit", "exit", "q", "thoát", ":q"):
        assert is_quit(q)
    assert not is_quit("what is X?")


def test_run_chat_loop_answers_until_quit() -> None:
    inputs = iter(["What is X?", "And Y?", "quit"])
    outputs: list[str] = []
    llm = ScriptedLLM(decisions=[], text="An answer.")

    run_chat_loop(
        "REPORT",
        llm,
        read_input=lambda _prompt: next(inputs),
        write_output=outputs.append,
        language="en",
    )
    # Two questions answered (third input quits); the intro line is also written.
    assert llm.generate_calls == 2
    assert outputs.count("An answer.") == 2


def test_run_chat_loop_stops_on_eof() -> None:
    def raise_eof(_prompt: str) -> str:
        raise EOFError

    outputs: list[str] = []
    run_chat_loop("REPORT", ScriptedLLM(decisions=[]), raise_eof, outputs.append)
    # No answers, just the intro line.
    assert all("Ask follow-up" in o or o == "" for o in outputs)
