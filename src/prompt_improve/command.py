"""Main entry point — UserPromptSubmit hook for Claude Code / Codex / Gemini."""

from __future__ import annotations

import json
import os
import sys

from prompt_improve.features.detect import decide_mode, detect_trivial, has_concrete_target
from prompt_improve.features.hints import continuation_context
from prompt_improve.features.improve import route_and_improve
from prompt_improve.features.rules import rule_based_suggestions
from prompt_improve.features.target import TargetProfile, target_profile_from_request


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


def _try_improve(
    prompt: str,
    mode: str,
    cwd: str | None,
    target: TargetProfile | None = None,
) -> tuple[str | None, str, str]:
    """Try LLM improvement, then rule-based fallback.

    Returns (improved, source, effective_mode). The effective_mode may differ
    from the input mode when rewrite falls back to clarify.
    """
    if mode == "rewrite":
        deterministic = continuation_context(prompt, cwd)
        if deterministic:
            return deterministic, "memory:currentTask", "rewrite"

    target = target or target_profile_from_request()
    result = route_and_improve(prompt, mode, cwd, target)
    if result:
        return result[0], result[1], mode

    if mode == "rewrite":
        result = route_and_improve(prompt, "clarify", cwd, target)
        if result:
            return result[0], result[1], "clarify"

    fallback = rule_based_suggestions(prompt)
    return fallback, "fallback:rules", mode


def main() -> None:
    cwd: str | None = None
    data: dict | None = None
    try:
        loaded = json.load(sys.stdin)
        data = loaded if isinstance(loaded, dict) else None
        if isinstance(data, dict):
            prompt = data.get("prompt", "").strip()
            cwd = data.get("cwd") or data.get("cwd_path")
        else:
            prompt = ""
    except (json.JSONDecodeError, OSError):
        prompt = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else sys.stdin.read().strip()
    target = target_profile_from_request(data)

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

    improved, source, effective_mode = _try_improve(prompt, mode, cwd, target)

    if not improved:
        _passthrough()
        return

    is_rewrite = source.startswith("memory:") or effective_mode == "rewrite"
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
