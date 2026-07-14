"""Ollama client wrapper: model discovery, selection, and role-based routing."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from prompt_improve.shared.config import (
    _ROLE_MODEL_MAP,
    OLLAMA_AUTOSTART,
    OLLAMA_LOG,
    OLLAMA_MODEL_CANDIDATES,
    OLLAMA_PID,
    OLLAMA_URL,
)


def _get_json(path: str, timeout: float) -> dict | None:
    try:
        # OLLAMA_URL is normalized to http loopback in shared.config.
        url = f"{OLLAMA_URL.rstrip('/')}{path}"
        with urlopen(url, timeout=timeout) as response:  # nosemgrep
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


def _spawn_ollama() -> bool:
    """Launch ``ollama serve`` detached and record its pid. Best-effort."""
    try:
        os.makedirs(os.path.dirname(OLLAMA_LOG), exist_ok=True)
    except OSError:
        return False
    proc = _launch_ollama_serve()
    if proc is None:
        return False
    try:
        with open(OLLAMA_PID, "w", encoding="utf-8") as f:
            f.write(str(proc.pid))
    except OSError:
        return False
    return True


def _launch_ollama_serve() -> subprocess.Popen | None:  # type: ignore[type-arg]
    """Start ollama serve with stdout redirected to the log file."""
    try:
        log = open(OLLAMA_LOG, "ab")
    except OSError:
        return None
    try:
        return subprocess.Popen(
            ["ollama", "serve"],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None
    finally:
        # Popen has already inherited (and duplicated) the fd into the child at
        # fork/exec; the parent's own handle is no longer needed. Closing it here
        # avoids an fd leak + ResourceWarning while the detached daemon keeps
        # writing to the log via its own copy of the descriptor.
        log.close()


def start_ollama_best_effort() -> bool:
    """Start local Ollama if it is installed but not responding."""
    if not OLLAMA_AUTOSTART:
        return False
    if available_ollama_models():
        return True
    if not _spawn_ollama():
        return False
    for _ in range(6):
        time.sleep(0.25)
        if available_ollama_models():
            return True
    return False


def _normalize_model_name(name: str) -> str:
    # remove registry prefixes/usernames (e.g. hf.co/kai-os/Grug-12B-GGUF -> Grug-12B-GGUF)
    name = re.sub(r"^(?:[^/]+/){1,2}", "", name)
    # remove tags
    if ":" in name:
        name = name.split(":")[0]
    # remove host/quantization hints that vary by local install tag
    name = re.sub(r"_Q\d+K_\d+GB-GPU$", "", name, flags=re.I)
    name = re.sub(r"_Q\d+_\d+k_\d+GB-GPU$", "", name, flags=re.I)
    name = re.sub(r"_(?:UD_)?Q\d(?:_[A-Z0-9]+)*$", "", name, flags=re.I)
    return name.lower().replace("-", "").replace("_", "").replace(".", "")


def choose_ollama_model_for_role(role: str) -> tuple[str | None, list[str]]:
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

    # Map normalized names to actual available names for fallback matching
    norm_available: dict[str, str] = {}
    for actual in available:
        norm = _normalize_model_name(actual)
        if norm:
            norm_available[norm] = actual

    def find_match(cand: str) -> str | None:
        if cand in available:
            return cand
        cand_norm = _normalize_model_name(cand)
        return norm_available.get(cand_norm)

    role_candidates = _ROLE_MODEL_MAP.get(role, [])
    all_ordered: list[str] = []
    seen: set[str] = set()

    for model in role_candidates:
        match = find_match(model)
        if match and match not in seen:
            all_ordered.append(match)
            seen.add(match)

    for model in OLLAMA_MODEL_CANDIDATES:
        match = find_match(model)
        if match and match not in seen:
            all_ordered.append(match)
            seen.add(match)

    # Sorted so the leftover tail is deterministic — ``available`` is a set,
    # and set-iteration order would otherwise vary between hook invocations.
    for model in sorted(available):
        if model not in seen:
            all_ordered.append(model)
            seen.add(model)

    if not all_ordered:
        return None, []
    return all_ordered[0], all_ordered[1:]
