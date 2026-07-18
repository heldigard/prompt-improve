"""Best-effort file locking for latency-sensitive hooks."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows has no fcntl
    fcntl = None  # type: ignore[assignment]


@contextmanager
def try_exclusive_lock(handle: IO[str]) -> Iterator[bool]:
    """Acquire an exclusive lock without waiting.

    Metrics persistence is optional, so a busy POSIX lock becomes a skipped
    write. Platforms without ``fcntl`` retain best-effort append behavior.
    """
    if fcntl is None:
        yield True
        return

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        yield False
        return

    try:
        yield True
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
