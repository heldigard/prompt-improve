"""Main entry point — UserPromptSubmit hook for Claude Code / Codex / Gemini."""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from prompt_improve.features.detect import detect_trivial, decide_mode, has_concrete_target
from prompt_improve.features.hints import continuation_context
from prompt_improve.features.improve import route_and_improve
from prompt_improve.features.rules import rule_based_suggestions


def _passthrough() -> None:
    print(json.dumps({"continue": True}))


def _build_additional(improved: str, source: str, is_rewrite: bool) -> str:
    if is_rewrite:
        return (
            f"[Prompt expandido: {source}]\n\n"
            f"{improved}\n\n"
            f"[Usa esta expansión como especificación de trabajo. "
            f"La intención original del usuario prevalece sobre la expansión.]"
        )
    return f"[Mejora de prompt: {source}]\n\n{improved}"


def _try_improve(prompt: str, mode: str, cwd: Optional[str]) -> tuple[Optional[str], str]:
    """Try LLM improvement, then rule-based fallback. Returns (improved, source)."""
    if mode == "rewrite":
        deterministic = continuation_context(prompt, cwd)
        if deterministic:
            return deterministic, "memory:currentTask"

    result = route_and_improve(prompt, mode, cwd)
    if result:
        return result

    if mode == "rewrite":
        result = route_and_improve(prompt, "clarify", cwd)
        if result:
            return result

    fallback = rule_based_suggestions(prompt)
    return fallback, "fallback:rules"


def main() -> None:
    cwd: Optional[str] = None
    try:
        data = json.load(sys.stdin)
        if isinstance(data, dict):
            prompt = data.get("prompt", "").strip()
            cwd = data.get("cwd") or data.get("cwd_path")
        else:
            prompt = ""
    except (json.JSONDecodeError, OSError):
        prompt = sys.stdin.read().strip()

    if (
        "[NO_DELEGATE]" in prompt
        or "[NO_IMPROVE]" in prompt
        or "[CODEX_WORKER]" in prompt
        or "[NO_SWARM]" in prompt
        or os.environ.get("NO_DELEGATE")
        or os.environ.get("NO_IMPROVE")
        or os.environ.get("CODEX_WORKER")
        or os.environ.get("SWARM_WORKER")
    ):
        _passthrough()
        return

    if not prompt or detect_trivial(prompt):
        _passthrough()
        return

    mode = decide_mode(prompt)

    if mode == "rewrite" and has_concrete_target(prompt):
        _passthrough()
        return

    improved, source = _try_improve(prompt, mode, cwd)

    if not improved:
        _passthrough()
        return

    is_rewrite = source.startswith("memory:") or mode == "rewrite"
    additional = _build_additional(improved, source, is_rewrite)
    output = {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional,
        },
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
