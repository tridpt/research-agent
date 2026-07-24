"""Regression tests for local-file and outbound-network safety boundaries."""
from __future__ import annotations

import socket
from pathlib import Path

import httpx

from research_agent.fetch_tool import HttpFetchTool
from research_agent.local_documents import approved_pdf_path
from research_agent.url_safety import public_http_url_error


def _resolver(address: str):
    def resolve(_host, port, *, type):
        return [(socket.AF_INET, type, 6, "", (address, port))]

    return resolve


def test_public_http_url_error_rejects_non_public_destinations() -> None:
    assert public_http_url_error("https://example.test", resolver=_resolver("8.8.8.8")) is None
    assert "private" in public_http_url_error("https://example.test", resolver=_resolver("127.0.0.1"))
    assert "local" in public_http_url_error("http://localhost:8501")
    assert "only http" in public_http_url_error("file:///C:/secret.pdf")


def test_fetch_rechecks_redirect_destination_before_request() -> None:
    tool = HttpFetchTool(
        blocked_domains=frozenset(),
        per_source_char_limit=100,
        url_validator=lambda url: public_http_url_error(url, resolver=_resolver("8.8.8.8")),
    )

    class RedirectResponse:
        status_code = 302
        headers = {"Location": "http://127.0.0.1/admin"}
        url = httpx.URL("https://example.test/start")

        @property
        def is_redirect(self) -> bool:
            return True

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            return None

    class RedirectClient:
        calls: list[str] = []

        def stream(self, method, url):
            assert method == "GET"
            self.calls.append(url)
            return RedirectResponse()

    client = RedirectClient()
    tool._client = client  # type: ignore[assignment]
    outcome = tool.fetch("https://example.test/start")

    assert "unsafe redirect URL" in (outcome.error or "")
    assert client.calls == ["https://example.test/start"]


def test_fetch_rejects_private_peer_ip_after_connect() -> None:
    """DNS rebinding: hostname passes validation but connects to a private IP."""

    class _Stream:
        def get_extra_info(self, key):
            return ("127.0.0.1", 443) if key == "server_addr" else None

    class _RebindResponse:
        status_code = 200
        headers: dict[str, str] = {}
        url = httpx.URL("https://example.test/x")
        encoding = "utf-8"
        extensions = {"network_stream": _Stream()}

        @property
        def is_redirect(self) -> bool:
            return False

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            return None

        def iter_bytes(self):
            raise AssertionError("body must not be read from a rebound host")

    class _RebindClient:
        def stream(self, method, url):
            assert method == "GET"
            return _RebindResponse()

    tool = HttpFetchTool(
        blocked_domains=frozenset(),
        per_source_char_limit=100,
        url_validator=lambda url: public_http_url_error(url, resolver=_resolver("8.8.8.8")),
    )
    tool._client = _RebindClient()  # type: ignore[assignment]
    outcome = tool.fetch("https://example.test/x")

    assert not outcome.ok
    assert "unsafe peer address" in (outcome.error or "")


def test_approved_pdf_path_requires_exact_user_selection(tmp_path: Path) -> None:
    selected = tmp_path / "selected.pdf"
    selected.write_bytes(b"%PDF-1.4\n")
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"%PDF-1.4\n")

    approved, error = approved_pdf_path(str(selected), [selected])
    assert approved == selected.resolve()
    assert error is None

    rejected, error = approved_pdf_path(str(secret), [selected])
    assert rejected is None
    assert "not explicitly approved" in (error or "")
