"""Symlink-safe sys.path bootstrap + graceful imports of harness helpers.

The prompt-improve hook is reached three ways:
  1. Claude Code:  ``python3 ~/.claude/hooks/prompt-improve.py`` (the shim)
  2. Codex/Gemini: ``~/.codex|gemini/hooks/prompt-improve.py`` -> symlink to shim
  3. pytest:       ``import prompt_improve`` (installed via ``pip install -e``)

The helpers ``ollama_client`` and ``cheap_complete`` live under
``~/.claude/scripts/`` and are NOT on sys.path by default. Here we resolve the
harness root **absolutely** (``~/.claude``), which is correct for all entry
modes and does not depend on where the source tree happens to live.

Importing this module has the side effect of extending ``sys.path`` exactly once
(it is imported by ``prompt_improve/__init__.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_CLAUDE_ROOT = Path.home() / ".claude"
for _candidate in (_CLAUDE_ROOT / "scripts",):
    _s = str(_candidate)
    if _candidate.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

try:
    import ollama_client  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - env-dependent
    ollama_client = None  # type: ignore[assignment]

try:
    from cheap_llm import cheap_complete  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - env-dependent
    cheap_complete = None  # type: ignore[assignment]

__all__ = ["ollama_client", "cheap_complete"]
