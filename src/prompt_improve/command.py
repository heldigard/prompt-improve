"""Main entry point — UserPromptSubmit hook for Claude Code / Codex / Gemini."""

from __future__ import annotations

import json
import os
import sys
from time import monotonic

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
from prompt_improve.shared import metrics
from prompt_improve.shared.config import OLLAMA_TOTAL_TIMEOUT

MAX_STDIN_CHARS = 1_000_000


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
    deadline = monotonic() + OLLAMA_TOTAL_TIMEOUT
    result = route_and_improve(prompt, mode, cwd, target, deadline=deadline)
    if result:
        return result[0], result[1], mode

    if mode == "rewrite":
        result = route_and_improve(prompt, "clarify", cwd, target, deadline=deadline)
        if result:
            return result[0], result[1], "clarify"

    fallback = rule_based_suggestions(prompt)
    return fallback, "fallback:rules", mode


def _handle_cli_flags() -> bool:
    """Handle --version/--help early so a TTY stdin read never blocks. True when handled."""
    if len(sys.argv) <= 1:
        return False
    first_arg = sys.argv[1].strip()
    if first_arg in ("--version", "-v"):
        from prompt_improve import __version__

        print(f"prompt-improve version {__version__}")
        return True
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
        return True
    if first_arg in {"improve", "classify", "detect", "target"}:
        from prompt_improve.cli import main as cli_main

        cli_main(sys.argv[1:])
        return True
    return False


def _read_stdin_payload() -> tuple[str, str | None, dict | None, bool]:
    """Read stdin JSON-or-plain input. Returns (prompt, cwd, payload, content_read)."""
    try:
        content = sys.stdin.read(MAX_STDIN_CHARS + 1)
    except OSError:
        return "", None, None, False
    if len(content) > MAX_STDIN_CHARS:
        return "", None, None, True
    content = content.strip()
    if not content:
        return "", None, None, False
    try:
        loaded = json.loads(content)
    except json.JSONDecodeError:
        return content, None, None, True
    if not isinstance(loaded, dict):
        return content, None, None, True
    raw_prompt = loaded.get("prompt")
    prompt = raw_prompt.strip() if isinstance(raw_prompt, str) else ""
    raw_cwd = loaded.get("cwd") or loaded.get("cwd_path")
    cwd = raw_cwd if isinstance(raw_cwd, str) else None
    return prompt, cwd, loaded, True


def _worker_opt_out(prompt: str) -> bool:
    """Worker/marker opt-outs: never improve delegated or explicitly tagged prompts."""
    return bool(
        "[NO_DELEGATE]" in prompt
        or "[NO_IMPROVE]" in prompt
        or "[CODEX_WORKER]" in prompt
        or "[NO_SWARM]" in prompt
        or os.environ.get("NO_DELEGATE")
        or os.environ.get("NO_IMPROVE")
        or os.environ.get("CODEX_WORKER")
        or os.environ.get("SWARM_WORKER")
    )


def _improve_and_emit(prompt: str, cwd: str | None, data: dict | None, direct_cli: bool) -> None:
    """Run the improvement pipeline and emit hook JSON or direct-CLI text."""
    mode = decide_mode(prompt)

    # The hook cannot see prior turns. Preserve anaphoric prompts so the large
    # model can resolve them against its own conversation context.
    # Also preserve prompts that already give the large model an actionable
    # scope: unsolicited "clarification" can dilute a long, precise request
    # just as easily as a full rewrite can.
    if depends_on_conversation_context(prompt) or has_concrete_target(prompt):
        metrics.record("passthrough:concrete")
        print(prompt) if direct_cli else _passthrough()
        return

    target = target_profile_from_request(data)
    improved, source, effective_mode = _try_improve(prompt, mode, cwd, target)

    if not improved:
        metrics.record("passthrough:noimprove")
        print(prompt) if direct_cli else _passthrough()
        return

    metrics.record(source)

    # Rule-based fallback always yields clarify-style bullets, never a structured
    # rewrite spec. Labeling it as a rewrite would, in direct-CLI mode, drop the
    # user's original prompt (printing only suggestions) and, in hook mode,
    # mis-frame suggestions as a "work specification". Treat rules as clarification.
    is_rewrite = (
        source.startswith("memory:") or effective_mode == "rewrite"
    ) and source != "fallback:rules"
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


def main() -> None:
    if _handle_cli_flags():
        return

    # Determine input source: stdin (JSON or plain) vs arguments
    # If stdin is not a TTY (piped/redirected), try reading from it first
    # If stdin is a TTY, only read from it if we have no command-line arguments.
    use_stdin = not sys.stdin.isatty() or len(sys.argv) == 1

    prompt, cwd, data, content_read = ("", None, None, False)
    if use_stdin:
        prompt, cwd, data, content_read = _read_stdin_payload()

    direct_cli = False
    if not content_read and len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:]).strip()
        direct_cli = True

    try:
        if _worker_opt_out(prompt) or not prompt or detect_trivial(prompt):
            metrics.record("passthrough:trivial")
            print(prompt) if direct_cli else _passthrough()
            return

        try:
            _improve_and_emit(prompt, cwd, data, direct_cli)
        except Exception as exc:  # fail OPEN: the hook must never degrade prompt submission
            print(f"[prompt-improve] unexpected error, passing through: {exc}", file=sys.stderr)
            metrics.record("error")
            print(prompt) if direct_cli else _passthrough()
    finally:
        metrics.emit()


if __name__ == "__main__":
    main()
