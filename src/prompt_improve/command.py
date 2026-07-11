"""Main entry point — UserPromptSubmit hook for Claude Code / Codex / Gemini."""

from __future__ import annotations

import json
import os
import sys

from prompt_improve.features.detect import (
    decide_mode,
    depends_on_conversation_context,
    detect_trivial,
    has_concrete_target,
)
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


def _build_direct_output(original: str, improved: str, is_rewrite: bool) -> str:
    if is_rewrite:
        return improved
    return f"{original}\n\nPrompt improvement notes:\n{improved}"


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
    direct_cli = False
    prompt = ""

    # Check command-line arguments for options first to avoid blocking on stdin read when TTY is active
    if len(sys.argv) > 1:
        first_arg = sys.argv[1].strip()
        if first_arg in ("--version", "-v"):
            from prompt_improve import __version__

            print(f"prompt-improve version {__version__}")
            return
        if first_arg in ("--help", "-h"):
            print("prompt-improve — LLM-powered prompt improvement hook")
            print()
            print("Usage:")
            print("  python3 -m prompt_improve.command [prompt]")
            print("  Or pass a JSON payload containing 'prompt' and optionally 'cwd' via stdin.")
            print()
            print("Options:")
            print("  -v, --version  Show version")
            print("  -h, --help     Show this help message")
            return

    # Determine input source: stdin (JSON or plain) vs arguments
    # If stdin is not a TTY (piped/redirected), try reading from it first
    # If stdin is a TTY, only read from it if we have no command-line arguments.
    use_stdin = not sys.stdin.isatty() or len(sys.argv) == 1

    content_read = False
    if use_stdin:
        try:
            content = sys.stdin.read().strip()
            if content:
                content_read = True
                try:
                    loaded = json.loads(content)
                    data = loaded if isinstance(loaded, dict) else None
                    if isinstance(data, dict):
                        prompt = data.get("prompt", "").strip()
                        cwd = data.get("cwd") or data.get("cwd_path")
                    else:
                        prompt = content
                except json.JSONDecodeError:
                    prompt = content
        except OSError:
            pass

    if not content_read and len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:]).strip()
        direct_cli = True

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
        print(prompt) if direct_cli else _passthrough()
        return

    if not prompt or detect_trivial(prompt):
        print(prompt) if direct_cli else _passthrough()
        return

    mode = decide_mode(prompt)

    # The hook cannot see prior turns. Preserve anaphoric prompts so the large
    # model can resolve them against its own conversation context.
    if depends_on_conversation_context(prompt):
        print(prompt) if direct_cli else _passthrough()
        return

    # Preserve prompts that already give the large model an actionable scope.
    # This applies to both modes: unsolicited "clarification" can dilute a long,
    # precise request just as easily as a full rewrite can.
    if has_concrete_target(prompt):
        print(prompt) if direct_cli else _passthrough()
        return

    improved, source, effective_mode = _try_improve(prompt, mode, cwd, target)

    if not improved:
        print(prompt) if direct_cli else _passthrough()
        return

    is_rewrite = source.startswith("memory:") or effective_mode == "rewrite"
    if direct_cli:
        print(_build_direct_output(prompt, improved, is_rewrite))
        return

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
