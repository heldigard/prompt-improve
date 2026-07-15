"""Lightweight in-memory counters for the prompt-improve hook.

Recorded at decision points (cache hit, source of improvement, passthrough
reason) and emitted to stderr when ``OLLAMA_IMPROVE_METRICS=1`` (or DEBUG).
Optionally persisted as JSONL to ``~/.claude/state/prompt-improve/metrics.jsonl``
when ``OLLAMA_IMPROVE_METRICS_PERSIST=1`` — ops can graph or alert on it.

No persistence, no network, and negligible cost when disabled — the record is a
``Counter`` increment and ``emit`` short-circuits unless enabled, so the hot
path of an interactive hook is untouched in normal operation.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

_counts: Counter[str] = Counter()


def _enabled() -> bool:
    return os.environ.get("OLLAMA_IMPROVE_METRICS", "0") == "1" or (
        os.environ.get("OLLAMA_IMPROVE_DEBUG", "0") == "1"
    )


def _persist_enabled() -> bool:
    return os.environ.get("OLLAMA_IMPROVE_METRICS_PERSIST", "0") == "1"


def _metrics_dir() -> Path:
    return Path(
        os.environ.get(
            "OLLAMA_IMPROVE_METRICS_DIR",
            str(Path.home() / ".claude" / "state" / "prompt-improve"),
        )
    )


def record(source: str) -> None:
    """Tally one hook outcome keyed by its source label.

    Labels are free-form strings (e.g. ``cache:hit``, ``ollama``,
    ``passthrough:trivial``); they are aggregated verbatim in the emitted line.
    """
    _counts[source] += 1


def _persist_jsonl(items: dict[str, int]) -> None:
    """Append one JSONL record (fail-open). Disabled by default."""
    try:
        target = _metrics_dir()
        target.mkdir(parents=True, exist_ok=True)
        with (target / "metrics.jsonl").open("a") as fh:
            fh.write(
                json.dumps({"ts": int(time.time()), "counts": items}, separators=(",", ":")) + "\n"
            )
    except OSError:
        return


def emit(reset: bool = True) -> None:
    """Print counters to stderr and (optionally) append a JSONL record.

    Called once at the end of a hook invocation. ``reset`` clears the counters
    after emitting so the in-memory state does not leak across invocations
    within a long-lived process (tests, the console-script REPL).
    """
    if not _enabled() and not _persist_enabled():
        return
    if not _counts:
        return
    items = dict(_counts)
    if _enabled():
        try:
            text = ", ".join(f"{k}={v}" for k, v in sorted(items.items()))
            print(f"[prompt-improve metrics] {text}", file=sys.stderr)
        except OSError:
            pass
    if _persist_enabled():
        _persist_jsonl(items)
    if reset:
        _counts.clear()
