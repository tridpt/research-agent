"""GitHub repository lookup tool.

Fetches public repo metadata (description, stars, language, license, latest
release) via the GitHub REST API (no key needed for low-rate public access).
Parsing/formatting are pure; only ``fetch_github`` performs network I/O.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

GITHUB_API = "https://api.github.com/repos/{repo}"
USER_AGENT = "research-agent/0.1 (+https://github.com/tridpt/research-agent)"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubError(ValueError):
    """Raised when a repo identifier is invalid or the repo can't be read."""


@dataclass(frozen=True)
class RepoInfo:
    full_name: str
    description: str
    stars: int
    forks: int
    open_issues: int
    language: str
    license: str
    url: str
    latest_release: str = ""


def normalize_repo(raw: str) -> str:
    """Pure: accept 'owner/name' or a GitHub URL; return 'owner/name'.

    Raises GitHubError for anything that isn't a valid owner/name pair.
    """
    text = (raw or "").strip()
    text = re.sub(r"^https?://(www\.)?github\.com/", "", text, flags=re.IGNORECASE)
    text = text.strip("/")
    # Keep only owner/name if extra path segments were included.
    parts = text.split("/")
    if len(parts) >= 2:
        text = f"{parts[0]}/{parts[1]}"
    if text.endswith(".git"):
        text = text[:-4]
    if not _REPO_RE.match(text):
        raise GitHubError("expected a repository as 'owner/name'")
    return text


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_repo(payload: Any) -> RepoInfo:
    """Pure: parse a GitHub repo API response into RepoInfo."""
    if not isinstance(payload, dict):
        raise GitHubError("malformed response")
    full_name = str(payload.get("full_name") or "").strip()
    if not full_name:
        raise GitHubError("repository not found")
    license_obj = payload.get("license")
    license_id = ""
    if isinstance(license_obj, dict):
        spdx = license_obj.get("spdx_id")
        if spdx and spdx != "NOASSERTION":
            license_id = str(spdx)
    return RepoInfo(
        full_name=full_name,
        description=str(payload.get("description") or "").strip(),
        stars=_as_int(payload.get("stargazers_count")),
        forks=_as_int(payload.get("forks_count")),
        open_issues=_as_int(payload.get("open_issues_count")),
        language=str(payload.get("language") or "").strip(),
        license=license_id,
        url=str(payload.get("html_url") or f"https://github.com/{full_name}").strip(),
    )


def parse_release(payload: Any) -> str:
    """Pure: extract a short 'latest release' label, or '' if unavailable."""
    if not isinstance(payload, dict):
        return ""
    tag = str(payload.get("tag_name") or "").strip()
    if not tag:
        return ""
    published = str(payload.get("published_at") or "").strip()[:10]
    return f"{tag} ({published})" if published else tag


def format_repo(info: RepoInfo) -> str:
    """Pure: a compact, readable summary of a repository."""
    lines = [f"GitHub — {info.full_name}"]
    if info.description:
        lines.append(info.description)
    stats = f"⭐ {info.stars} stars · {info.forks} forks · {info.open_issues} open issues"
    if info.language:
        stats += f" · {info.language}"
    if info.license:
        stats += f" · {info.license}"
    lines.append(stats)
    if info.latest_release:
        lines.append(f"Latest release: {info.latest_release}")
    return "\n".join(lines)


def fetch_github(repo: str, *, timeout: float = 15.0) -> tuple[str, str]:
    """Fetch repo (and latest release) info; return (url, formatted content).

    Network I/O is isolated here so parsing/formatting stay pure. Raises
    GitHubError on any network or parsing failure.
    """
    import dataclasses

    import httpx

    name = normalize_repo(repo)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    try:
        resp = httpx.get(GITHUB_API.format(repo=name), timeout=timeout, headers=headers, follow_redirects=True)
        resp.raise_for_status()
        info = parse_repo(resp.json())
        release_resp = httpx.get(
            GITHUB_API.format(repo=name) + "/releases/latest",
            timeout=timeout, headers=headers, follow_redirects=True,
        )
        release = parse_release(release_resp.json()) if release_resp.status_code == 200 else ""
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise GitHubError(f"could not fetch repository: {exc}") from exc
    except ValueError as exc:  # pragma: no cover - invalid JSON
        raise GitHubError(f"invalid repository response: {exc}") from exc
    if release:
        info = dataclasses.replace(info, latest_release=release)
    return info.url, format_repo(info)
