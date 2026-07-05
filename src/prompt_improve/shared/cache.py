"""On-disk TTL cache for prompt improvement results."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from prompt_improve.shared.config import (
    CACHE_DIR,
    CACHE_SCHEMA_VERSION,
    CACHE_TTL_SECONDS,
)


def _find_memory_bank(root: Path) -> Path | None:
    """Walk parents to find the nearest .memory-bank/ directory."""
    for parent in [root, *root.parents]:
        if parent == parent.parent:
            break
        mb = parent / ".memory-bank"
        try:
            exists = mb.exists()
        except OSError:
            continue
        if exists:
            return mb
    return None


def _project_cache_scope(cwd: str | None) -> str:
    """Scope cache entries to the nearest project, not only prompt text."""
    if not cwd:
        return "global"
    try:
        root = Path(cwd).expanduser().resolve()
    except (OSError, ValueError):
        return cwd[:200]
    memory = _find_memory_bank(root)
    return str(memory.parent) if memory else str(root)


def _project_context_fingerprint(cwd: str | None) -> str:
    """Fingerprint memory files that influence prompt rewriting."""
    if not cwd:
        return "no-memory"
    try:
        root = Path(cwd).expanduser().resolve()
    except (OSError, ValueError):
        return "bad-cwd"
    memory = _find_memory_bank(root)
    if memory is None:
        return "no-memory"
    parts: list[str] = []
    for name in ("currentTask.md", "activeContext.md"):
        path = memory / name
        try:
            stat = path.stat()
        except OSError:
            continue
        parts.append(f"{name}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts) if parts else "empty-memory"


def _cache_key(prompt: str, mode: str, cwd: str | None = None) -> str:
    scope = _project_cache_scope(cwd)
    fingerprint = _project_context_fingerprint(cwd)
    return hashlib.sha256(
        f"{CACHE_SCHEMA_VERSION}:{mode}:{scope}:{fingerprint}:{prompt}".encode()
    ).hexdigest()[:32]


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def load_cached(prompt: str, mode: str, cwd: str | None = None) -> tuple[str, str] | None:
    if CACHE_TTL_SECONDS <= 0:
        return None
    path = _cache_path(_cache_key(prompt, mode, cwd))
    if not path.exists():
        return None
    try:
        if time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
            path.unlink(missing_ok=True)
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("text"), data.get("source")
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def save_cached(prompt: str, mode: str, text: str, source: str, cwd: str | None = None) -> None:
    if CACHE_TTL_SECONDS <= 0:
        return
    path = _cache_path(_cache_key(prompt, mode, cwd))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"text": text, "source": source}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass
