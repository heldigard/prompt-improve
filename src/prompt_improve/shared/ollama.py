"""Ollama client wrapper: model discovery, selection, and role-based routing."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Optional
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
import json

from prompt_improve.shared import compat
from prompt_improve.shared.config import (
    OLLAMA_URL,
    OLLAMA_LOG,
    OLLAMA_PID,
    OLLAMA_AUTOSTART,
    OLLAMA_MODEL_CANDIDATES,
    _ROLE_MODEL_MAP,
)


def _get_json(path: str, timeout: float) -> Optional[dict]:
    try:
        with urlopen(f"{OLLAMA_URL.rstrip('/')}{path}", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None


def available_ollama_models() -> list[str]:
    data = _get_json("/api/tags", timeout=1.5)
    if not data:
        return []
    models = data.get("models", [])
    names = []
    for model in models:
        if isinstance(model, dict) and isinstance(model.get("name"), str):
            names.append(model["name"])
    return names


def start_ollama_best_effort() -> bool:
    """Start local Ollama if it is installed but not responding."""
    if not OLLAMA_AUTOSTART:
        return False
    if available_ollama_models():
        return True
    try:
        os.makedirs(os.path.dirname(OLLAMA_LOG), exist_ok=True)
        log = open(OLLAMA_LOG, "ab")
        proc = subprocess.Popen(
            ["ollama", "serve"],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        log.close()
        with open(OLLAMA_PID, "w", encoding="utf-8") as f:
            f.write(str(proc.pid))
    except OSError:
        return False
    for _ in range(6):
        time.sleep(0.25)
        if available_ollama_models():
            return True
    return False


def ordered_ollama_models() -> list[str]:
    available = available_ollama_models()
    if not available:
        start_ollama_best_effort()
        available = available_ollama_models()
    if not available:
        return []
    available_set = set(available)
    ordered = []
    for candidate in OLLAMA_MODEL_CANDIDATES:
        if candidate in available_set:
            ordered.append(candidate)
    ordered.extend(model for model in available if model not in ordered)
    return ordered


def choose_ollama_model() -> Optional[str]:
    models = ordered_ollama_models()
    return models[0] if models else None


def choose_ollama_model_for_role(role: str) -> tuple[Optional[str], list[str]]:
    """Pick the best available model for a specific task role.

    Returns (primary_model, fallback_models). The primary gets full timeout;
    fallbacks get reduced timeout (caller already handles this).

    Role-specific candidates from _ROLE_MODEL_MAP are tried first, then
    OLLAMA_MODEL_CANDIDATES as global fallback, then any available model."""
    available = set(available_ollama_models())
    if not available:
        start_ollama_best_effort()
        available = set(available_ollama_models())
    if not available:
        return None, []

    role_candidates = _ROLE_MODEL_MAP.get(role, [])
    all_ordered: list[str] = []
    seen: set[str] = set()

    for model in role_candidates:
        if model in available and model not in seen:
            all_ordered.append(model)
            seen.add(model)

    for model in OLLAMA_MODEL_CANDIDATES:
        if model in available and model not in seen:
            all_ordered.append(model)
            seen.add(model)

    for model in available:
        if model not in seen:
            all_ordered.append(model)
            seen.add(model)

    if not all_ordered:
        return None, []
    return all_ordered[0], all_ordered[1:]
