"""Interactive follow-up chat over a finished report (CLI).

After a report is written, the user can ask follow-up questions answered ONLY
from that report — the same grounding the web UI uses. ``build_chat_messages``
is pure; ``run_chat_loop`` drives the terminal loop with injected I/O so it can
be tested without a real terminal.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from .llm import LLMProvider, Message

_CHAT_SYSTEM = (
    "You are answering follow-up questions about a research report. Base your "
    "answers ONLY on the report below; if the report does not contain the "
    "answer, say so honestly. Be concise."
)
_LANG_NOTE = {"vi": " Trả lời bằng tiếng Việt.", "en": " Answer in English."}
_QUIT_WORDS = {"", "exit", "quit", "q", "thoat", "thoát", ":q"}


def build_chat_messages(
    report_markdown: str,
    history: Sequence[tuple[str, str]],
    follow_up: str,
    language: str | None = None,
) -> list[Message]:
    """Pure: assemble grounded chat messages (system + report + history + new Q)."""
    system = _CHAT_SYSTEM + _LANG_NOTE.get(language or "", "")
    messages = [
        Message(role="system", content=system),
        Message(role="user", content=f"REPORT:\n{report_markdown}"),
    ]
    for role, content in history:
        messages.append(Message(role=role, content=content))
    messages.append(Message(role="user", content=follow_up))
    return messages


def is_quit(text: str) -> bool:
    """Pure: True if the input signals the user wants to stop chatting."""
    return text.strip().lower() in _QUIT_WORDS


def run_chat_loop(
    report_markdown: str,
    llm: LLMProvider,
    read_input: Callable[[str], str],
    write_output: Callable[[str], None],
    language: str | None = None,
) -> None:
    """Drive an interactive follow-up Q&A loop until the user quits.

    ``read_input(prompt)`` returns the next user line (raise EOFError to stop);
    ``write_output(text)`` prints an answer. The report and prior turns ground
    every answer.
    """
    history: list[tuple[str, str]] = []
    write_output("\nAsk follow-up questions about the report (empty line or 'quit' to exit).")
    while True:
        try:
            follow_up = read_input("\n> ")
        except (EOFError, KeyboardInterrupt):
            break
        if is_quit(follow_up):
            break
        messages = build_chat_messages(report_markdown, history, follow_up.strip(), language)
        try:
            answer = llm.generate(messages)
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on errors
            write_output(f"(error: {exc})")
            continue
        write_output(answer)
        history.append(("user", follow_up.strip()))
        history.append(("assistant", answer))
