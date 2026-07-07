"""Loopback-only Ollama URL helpers."""

from __future__ import annotations

from urllib.parse import urlparse

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def normalize_ollama_url(value: str | None = None) -> str:
    """Return a safe Ollama base URL, falling back to loopback for unsafe input."""
    candidate = (value or DEFAULT_OLLAMA_URL).strip() or DEFAULT_OLLAMA_URL
    parsed = urlparse(candidate)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
        return DEFAULT_OLLAMA_URL
    port = f":{parsed.port}" if parsed.port else ""
    return f"http://{parsed.hostname}{port}"
