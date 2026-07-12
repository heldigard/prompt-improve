"""Loopback-only Ollama URL helpers."""

from __future__ import annotations

from urllib.parse import urlparse

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


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
        or hostname not in LOOPBACK_HOSTS
        or has_credentials
        or parsed.path not in ("", "/")
        or parsed.params
        or parsed.query
        or parsed.fragment
        or (port is not None and port == 0)
    ):
        return DEFAULT_OLLAMA_URL
    rendered_host = f"[{hostname}]" if hostname == "::1" else hostname
    rendered_port = f":{port}" if port is not None else ""
    return f"http://{rendered_host}{rendered_port}"
