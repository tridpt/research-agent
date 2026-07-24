"""Pure configuration helpers for the Streamlit UI.

These functions contain no Streamlit calls so they can be unit-tested in
isolation. ``app.py`` wires them to widgets, ``st.secrets``, and the process
environment. Keeping the credential/endpoint policy here makes the security
boundary explicit and independently verifiable.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from research_agent.errors import ConfigError

# Provider presets: label -> (base_url, default_model).
PRESETS: dict[str, tuple[str, str]] = {
    "Groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b"),
    "Gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash-lite"),
    "OpenAI": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "Khác (tùy chỉnh)": ("", ""),
}

QUALITY_LABELS_VI: dict[str, str] = {"high": "Cao", "medium": "Trung bình", "low": "Thấp"}

# Secret keys that must never be pre-filled into a browser widget.
SECRET_CONFIG_KEYS: frozenset[str] = frozenset(
    {"RESEARCH_AGENT_API_KEY", "RESEARCH_AGENT_TAVILY_API_KEY"}
)

# Built-in LLM hosts always permitted for the web UI's custom-endpoint path.
DEFAULT_ALLOWED_LLM_HOSTS: frozenset[str] = frozenset(
    {"api.groq.com", "generativelanguage.googleapis.com", "api.openai.com"}
)


def load_env_file(env_path: Path) -> dict[str, str]:
    """Parse a simple ``KEY=value`` .env file into a dict (missing file -> {})."""
    data: dict[str, str] = {}
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def parse_allowed_hosts(configured: str) -> frozenset[str]:
    """Merge the built-in LLM hosts with a comma-separated maintainer allowlist."""
    extras = {
        host.strip().rstrip(".").lower()
        for host in (configured or "").split(",")
        if host.strip()
    }
    return DEFAULT_ALLOWED_LLM_HOSTS | extras


def validated_llm_base_url(value: str, allowed_hosts: frozenset[str]) -> str:
    """Enforce the web UI's HTTPS and exact-host allowlist boundary.

    Returns a normalized ``https://host[:port][/path]`` URL, or raises
    ``ConfigError`` when the scheme, hostname, credentials, or query/fragment
    violate the policy, or the host is not in ``allowed_hosts``.
    """
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise ConfigError("LLM Base URL không hợp lệ.") from exc
    host = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme.lower() != "https":
        raise ConfigError("LLM Base URL phải sử dụng HTTPS trong web UI.")
    if not host or parsed.username or parsed.password:
        raise ConfigError("LLM Base URL phải có hostname hợp lệ và không chứa credentials.")
    if parsed.query or parsed.fragment:
        raise ConfigError("LLM Base URL không được chứa query string hoặc fragment.")
    if host not in allowed_hosts:
        raise ConfigError(
            "Hostname LLM chưa được cho phép. Quản trị viên phải thêm hostname chính xác "
            "vào RESEARCH_AGENT_ALLOWED_LLM_HOSTS."
        )
    default_port = port in (None, 443)
    authority = host if default_port else f"{host}:{port}"
    path = parsed.path.rstrip("/")
    return f"https://{authority}{path}"
