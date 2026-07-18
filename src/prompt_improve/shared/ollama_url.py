"""Loopback-only Ollama URL helpers."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def _is_loopback_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def normalize_ollama_url(value: str | None = None) -> str:
    """Return a safe Ollama base URL, falling back to loopback for unsafe input."""
    candidate = (value or DEFAULT_OLLAMA_URL).strip() or DEFAULT_OLLAMA_URL
    try:
        parsed = urlparse(candidate)
        hostname = parsed.hostname
        port = parsed.port
        has_credentials = parsed.username is not None or parsed.password is not None
    except (UnicodeError, ValueError):
        return DEFAULT_OLLAMA_URL
    if (
        parsed.scheme != "http"
        or not _is_loopback_host(hostname)
        or has_credentials
        or parsed.path not in ("", "/")
        or parsed.params
        or parsed.query
        or parsed.fragment
        or (port is not None and port == 0)
    ):
        return DEFAULT_OLLAMA_URL
    assert hostname is not None  # established by _is_loopback_host above
    rendered_host = f"[{hostname}]" if ":" in hostname else hostname
    rendered_port = f":{port}" if port is not None else ""
    return f"http://{rendered_host}{rendered_port}"
