"""End-to-end tests for prompt_improve.command.main() — the UserPromptSubmit hook entry point (passthrough, cwd extraction, additional-context shaping, CLI flags, direct-argv mode)."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile


def _run_main_via_stdin(prompt: str, cwd: str | None = None, env: dict | None = None):
    """Drive command.main() as if invoked by Claude Code's hook runtime."""
    from prompt_improve import command

    payload = {"prompt": prompt}
    if cwd is not None:
        payload["cwd"] = cwd
    stdin_bytes = json.dumps(payload).encode("utf-8")
    saved_stdin = sys.stdin
    saved_stdout = sys.stdout
    saved_env = {
        k: os.environ.get(k)
        for k in (
            "NO_DELEGATE",
            "NO_IMPROVE",
            "CODEX_WORKER",
            "SWARM_WORKER",
        )
    }
    try:
        sys.stdin = io.BytesIO(stdin_bytes)
        sys.stdout = io.StringIO()
        if env:
            for k, v in env.items():
                os.environ[k] = v
                os.environ.pop(k, None) if v is None else None
        command.main()
        return sys.stdout.getvalue()
    finally:
        sys.stdin = saved_stdin
        sys.stdout = saved_stdout
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _run_main_via_argv(*args: str):
    """Drive command.main() as a direct CLI helper, not as a hook."""
    from prompt_improve import command

    saved_stdin = sys.stdin
    saved_stdout = sys.stdout
    saved_argv = sys.argv
    try:
        sys.stdin = io.StringIO("")
        sys.stdout = io.StringIO()
        sys.argv = ["prompt-improve.py", *args]
        command.main()
        return sys.stdout.getvalue()
    finally:
        sys.stdin = saved_stdin
        sys.stdout = saved_stdout
        sys.argv = saved_argv


def test_main_passthrough_on_no_delegate_tag():
    """[NO_DELEGATE] in prompt must passthrough without improvement."""
    import prompt_improve.command as cmd_mod

    stdin_data = json.dumps({"prompt": "fix it [NO_DELEGATE]"})
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin_data)
    captured = {}
    old_print = print

    def fake_print(*args, **_kwargs):
        captured["output"] = args[0]

    import builtins

    builtins.print = fake_print
    try:
        cmd_mod.main()
    finally:
        sys.stdin = old_stdin
        builtins.print = old_print
    out = json.loads(captured["output"])
    assert out["continue"] is True
    assert "hookSpecificOutput" not in out


def test_main_passthrough_on_empty_prompt():
    """Empty prompt must passthrough."""
    import prompt_improve.command as cmd_mod

    stdin_data = json.dumps({"prompt": ""})
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin_data)
    captured = {}

    import builtins

    old_print = print
    builtins.print = lambda *a, **k: captured.update({"output": a[0]})
    try:
        cmd_mod.main()
    finally:
        sys.stdin = old_stdin
        builtins.print = old_print
    out = json.loads(captured["output"])
    assert out["continue"] is True
    assert "hookSpecificOutput" not in out


def test_main_passthrough_on_trivial():
    """Trivial prompt (e.g. 'ok') must passthrough."""
    import prompt_improve.command as cmd_mod

    stdin_data = json.dumps({"prompt": "ok"})
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin_data)
    captured = {}

    import builtins

    old_print = print
    builtins.print = lambda *a, **k: captured.update({"output": a[0]})
    try:
        cmd_mod.main()
    finally:
        sys.stdin = old_stdin
        builtins.print = old_print
    out = json.loads(captured["output"])
    assert out["continue"] is True
    assert "hookSpecificOutput" not in out


def test_main_extracts_cwd_from_stdin():
    """main() reads cwd from the JSON payload."""
    import prompt_improve.command as cmd_mod

    cwd = tempfile.mkdtemp()
    stdin_data = json.dumps({"prompt": "continua", "cwd": cwd})
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin_data)
    captured = {}

    import builtins

    old_print = print
    builtins.print = lambda *a, **k: captured.update({"output": a[0]})

    orig_try = cmd_mod._try_improve

    def spy_try(prompt, mode, c, target=None):
        captured["cwd_received"] = c
        return None, "test", mode

    cmd_mod._try_improve = spy_try
    try:
        cmd_mod.main()
    finally:
        sys.stdin = old_stdin
        builtins.print = old_print
        cmd_mod._try_improve = orig_try
    assert captured.get("cwd_received") == cwd


def test_main_builds_rewrite_additional_context():
    """Rewrite mode with memory: source produces expansion context."""
    import prompt_improve.command as cmd_mod

    result = cmd_mod._build_additional("expanded spec", "memory:currentTask", True)
    assert "Prompt expandido" in result
    assert "expanded spec" in result
    assert "intención original" in result


def test_main_builds_clarify_additional_context():
    """Clarify mode produces improvement context without expansion wrapper."""
    import prompt_improve.command as cmd_mod

    result = cmd_mod._build_additional("- Check auth", "ollama:model", False)
    assert "Mejora de prompt" in result
    assert "- Check auth" in result
    assert "expandido" not in result.lower()


def test_try_improve_rewrite_fallback_to_clarify():
    """When rewrite returns None but clarify succeeds, effective_mode is 'clarify'."""
    import prompt_improve.command as cmd_mod

    orig_route = cmd_mod.route_and_improve
    orig_cont = cmd_mod.continuation_context
    orig_rules = cmd_mod.rule_based_suggestions
    cmd_mod.continuation_context = lambda p, c: None
    call_count = {"n": 0}

    def fake_route(prompt, mode, cwd, target=None):
        call_count["n"] += 1
        if mode == "rewrite":
            return None
        return ("clarified result", "ollama:test")

    cmd_mod.route_and_improve = fake_route
    cmd_mod.rule_based_suggestions = lambda p: None
    try:
        result = cmd_mod._try_improve("fix it", "rewrite", None)
        assert result[0] == "clarified result"
        assert result[2] == "clarify"  # effective_mode fell back
        assert call_count["n"] == 2  # rewrite then clarify
    finally:
        cmd_mod.route_and_improve = orig_route
        cmd_mod.continuation_context = orig_cont
        cmd_mod.rule_based_suggestions = orig_rules


def test_command_main_passthrough_on_no_improve_marker():
    """[NO_IMPROVE] bypasses everything — emits a bare continue=true."""
    out = _run_main_via_stdin("implement the feature", env={"NO_IMPROVE": "1"})
    assert json.loads(out) == {"continue": True}


def test_command_main_passthrough_on_trivial_prompt():
    """Short acknowledgments must not invoke the LLM."""
    out = _run_main_via_stdin("ok thanks")
    assert json.loads(out) == {"continue": True}


def test_command_main_preserves_actionable_research_prompt():
    """Regression: a small local model must not reinterpret a named ranking
    review as a language migration or generic quality scan."""
    prompt = (
        "revisa ollama bech para establecer el modelo numero uno real y "
        "corregir la deuda mencionada"
    )
    out = _run_main_via_stdin(prompt, cwd="/home/eldi/codeq")
    assert json.loads(out) == {"continue": True}


def test_command_main_preserves_long_multi_repo_scope():
    prompt = (
        "Revisa prompt-improve, smart-trim, ollama-client y ollama-bench. "
        "Analiza sus contratos y corrige cualquier deriva verificable sin "
        "sacrificar la precision del modelo principal."
    )
    out = _run_main_via_stdin(prompt, cwd="/home/eldi/prompt-improve")
    assert json.loads(out) == {"continue": True}


def test_command_main_falls_through_when_no_model_available():
    """When LLM fails AND rule fallback yields nothing, emit bare continue."""
    # "asdfgh" with no TASK_VERBS and no Spanish markers — rule-based yields
    # nothing and we mock call_ollama_rewrite to return None (cold/dead daemon).
    import prompt_improve.command as cmd

    orig = cmd.route_and_improve
    cmd.route_and_improve = lambda _p, _mode, _cwd=None, target=None: None
    try:
        out = _run_main_via_stdin("asdfgh qwerty", cwd="/nonexistent")
    finally:
        cmd.route_and_improve = orig
    # Either bare continue (no improvement available) or hint — but never raises.
    parsed = json.loads(out)
    assert parsed.get("continue") is True


def test_command_passthrough_for_conversation_context_reference():
    """The hook must not rewrite evidence it cannot see but the brain can."""
    import prompt_improve.command as cmd

    original = cmd.route_and_improve

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("local model must not be called")

    cmd.route_and_improve = fail_if_called
    try:
        out = _run_main_via_stdin("arregla lo que hablamos ayer", cwd="/nonexistent")
    finally:
        cmd.route_and_improve = original
    assert json.loads(out) == {"continue": True}


def test_command_main_emits_additional_context_on_rewrite():
    """Happy path: rewrite mode routes through an LLM, wraps the output as
    hookSpecificOutput.additionalContext (NOT a user-facing question)."""
    import prompt_improve.command as cmd

    def fake_route(_prompt, _mode, _cwd=None, target=None):
        return ("Tarea: Hacer X.\n\nContexto: y.", "ollama:fake", "rewrite")

    orig = cmd.route_and_improve
    cmd.route_and_improve = fake_route
    # "implementa la funcion foo" passes detect_trivial (matches TASK_VERBS)
    # and avoids has_concrete_target (no file/path substring).
    try:
        out = _run_main_via_stdin("implementa la funcion foo", cwd="/nonexistent")
    finally:
        cmd.route_and_improve = orig
    parsed = json.loads(out)
    ctx = parsed["hookSpecificOutput"]["additionalContext"]
    assert "[Prompt expandido" in ctx
    assert "fake" in ctx
    assert "Tarea" in ctx


def test_command_main_direct_cli_outputs_plain_improved_prompt():
    """Direct enhance/argv mode emits text for shell wrappers, not hook JSON."""
    import prompt_improve.command as cmd

    def fake_route(_prompt, _mode, _cwd=None, target=None):
        return ("Task: Implement X.", "ollama:fake")

    orig = cmd.route_and_improve
    cmd.route_and_improve = fake_route
    try:
        out = _run_main_via_argv("implementa", "la", "funcion", "foo")
    finally:
        cmd.route_and_improve = orig
    assert out.strip() == "Task: Implement X."
    assert "hookSpecificOutput" not in out


def test_command_main_version_flags_print_version_and_return_early():
    """--version / -v print the version and short-circuit before stdin/LLM work.

    Regression guard for the CLI-flag branch added alongside the input-source
    rewrite: the flag must return before any stdin read (so it never blocks on
    a TTY) and must emit plain text, never hook JSON.
    """
    from prompt_improve import __version__

    for flag in ("--version", "-v"):
        out = _run_main_via_argv(flag)
        assert out.strip() == f"prompt-improve version {__version__}"
        assert "hookSpecificOutput" not in out
        assert "Usage" not in out


def test_command_main_help_flags_print_usage_and_return_early():
    """--help / -h print usage text and short-circuit before stdin/LLM work."""
    for flag in ("--help", "-h"):
        out = _run_main_via_argv(flag)
        assert "prompt-improve — LLM-powered prompt improvement hook" in out
        assert "Usage:" in out
        assert "python3 -m prompt_improve.command [prompt]" in out
        assert "hookSpecificOutput" not in out
