"""Network safety checks for outbound web fetching.

The research agent follows model-selected links, so URL validation must not
rely on a prompt alone.  This module rejects non-web URLs and destinations on
private or machine-local networks before a request is made.
"""
from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

Resolver = Callable[..., list[tuple]]


def public_ip_error(address: str) -> str | None:
    """Return an error unless ``address`` is a single global (public) IP.

    Shared by the pre-request URL check and the post-connect peer-IP check so
    both apply an identical policy against loopback, private, link-local, and
    reserved ranges.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return "hostname resolved to an invalid address"
    if not ip.is_global:
        return "private, loopback, link-local, or reserved addresses are not allowed"
    return None


def public_http_url_error(url: str, resolver: Resolver = socket.getaddrinfo) -> str | None:
    """Return an explanatory error unless ``url`` resolves only to public IPs.

    A DNS name with even one non-public answer is rejected.  This conservative
    policy prevents a hostname from selecting a private address via a second
    DNS answer or an IPv4/IPv6 fallback.
    """
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "invalid URL"

    if parsed.scheme.lower() not in {"http", "https"}:
        return "only http and https URLs are allowed"
    if not parsed.hostname:
        return "URL has no hostname"
    if parsed.username or parsed.password:
        return "URLs with embedded credentials are not allowed"

    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return "local hostnames are not allowed"

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    try:
        if literal_ip is not None:
            addresses = {str(literal_ip)}
        else:
            port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
            addresses = {info[4][0] for info in resolver(host, port, type=socket.SOCK_STREAM)}
    except (OSError, ValueError):
        return "hostname could not be resolved"
    if not addresses:
        return "hostname could not be resolved"

    for address in addresses:
        error = public_ip_error(address)
        if error is not None:
            return error
    return None
