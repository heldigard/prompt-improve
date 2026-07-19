"""Ollama client wrapper: model discovery, selection, and role-based routing."""

from __future__ import annotations

import json
import os
import re
import shutil
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

MAX_OLLAMA_RESPONSE_BYTES = 1_048_576

# Models that only produce vectors must never enter the improve chain tail.
# When preferred chat models are unavailable, the previous logic appended every
# name from /api/tags — including nomic-embed-text / bge-m3 / embeddinggemma —
# which then "succeeds" with unusable garbage under the shared wall-clock budget.
_NON_CHAT_MODEL_RE = re.compile(
    r"(?:^|[:/_.-])(?:embed(?:ding)?|bge[-_]?|e5[-_]?|minilm|nomic[-_]?embed|gte[-_]?)",
    re.IGNORECASE,
)


def _is_chat_model(name: str) -> bool:
    """True when the Ollama tag looks usable for chat completion (not embeddings)."""
    return bool(name) and _NON_CHAT_MODEL_RE.search(name) is None


def _get_json(path: str, timeout: float) -> dict | None:
    try:
        # OLLAMA_URL is normalized to http loopback in shared.config.
        url = f"{OLLAMA_URL.rstrip('/')}{path}"
        with urlopen(url, timeout=timeout) as response:  # nosemgrep
            raw = response.read(MAX_OLLAMA_RESPONSE_BYTES + 1)
            if len(raw) > MAX_OLLAMA_RESPONSE_BYTES:
                return None
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else None
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


def _systemctl_start_ollama() -> bool:
    """Start Ollama through systemd when a unit exists.

    On native Linux the daemon is a proper service (this host ships an enabled
    system unit); starting it through the service manager keeps supervision,
    logging, and GPU/env wiring in systemd instead of forking a rogue second
    ``ollama serve`` that competes with the managed unit. Nonzero exits (no
    unit, no polkit auth, systemctl missing) degrade to the nohup fallback.
    """
    if shutil.which("systemctl") is None:
        return False
    for scope in (["--user"], []):
        base = ["systemctl", *scope]
        try:
            has_unit = subprocess.run(
                [*base, "cat", "ollama.service"],
                capture_output=True,
                timeout=3,
                check=False,
            )
            if has_unit.returncode != 0:
                continue
            started = subprocess.run(
                [*base, "start", "ollama"],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if started.returncode == 0:
            return True
    return False


def _spawn_ollama() -> bool:
    """Launch Ollama (systemd first, detached ``ollama serve`` fallback). Best-effort."""
    if _systemctl_start_ollama():
        return True
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
    # systemd-managed units can take a little longer than a bare fork to report
    # ready; keep the total wait bounded so the hook latency stays predictable.
    for _ in range(10):
        time.sleep(0.3)
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
    for actual in sorted(available):
        norm = _normalize_model_name(actual)
        if norm:
            norm_available.setdefault(norm, actual)

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
    # Skip embedding-only tags: they burn the shared timeout without improving.
    for model in sorted(available):
        if model not in seen and _is_chat_model(model):
            all_ordered.append(model)
            seen.add(model)

    if not all_ordered:
        return None, []
    return all_ordered[0], all_ordered[1:]
