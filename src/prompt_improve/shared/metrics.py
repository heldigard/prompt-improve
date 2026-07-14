"""Lightweight in-memory counters for the prompt-improve hook.

Recorded at decision points (cache hit, source of improvement, passthrough
reason) and emitted to stderr when ``OLLAMA_IMPROVE_METRICS=1`` (or DEBUG).
No persistence, no network, and negligible cost when disabled — the record is a
``Counter`` increment and ``emit`` short-circuits unless enabled, so the hot
path of an interactive hook is untouched in normal operation.
"""

from __future__ import annotations

import os
import sys
from collections import Counter

_counts: Counter[str] = Counter()


def _enabled() -> bool:
    return os.environ.get("OLLAMA_IMPROVE_METRICS", "0") == "1" or (
        os.environ.get("OLLAMA_IMPROVE_DEBUG", "0") == "1"
    )


def record(source: str) -> None:
    """Tally one hook outcome keyed by its source label.

    Labels are free-form strings (e.g. ``cache:hit``, ``ollama``,
    ``passthrough:trivial``); they are aggregated verbatim in the emitted line.
    """
    _counts[source] += 1


def emit(reset: bool = True) -> None:
    """Print the counters to stderr when metrics are enabled. Fail-open.

    Called once at the end of a hook invocation. ``reset`` clears the counters
    after emitting so the in-memory state does not leak across invocations
    within a long-lived process (tests, the console-script REPL).
    """
    if not _enabled() or not _counts:
        return
    try:
        items = ", ".join(f"{k}={v}" for k, v in sorted(_counts.items()))
        print(f"[prompt-improve metrics] {items}", file=sys.stderr)
    except OSError:
        return
    if reset:
        _counts.clear()
