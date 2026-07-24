"""Tests for the prompt-improve CLI (offline replay surface)."""

from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path


def _run(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "prompt_improve.cli", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, (proc.stdout or "").strip()


def test_cli_detect_returns_json() -> None:
    rc, out = _run("detect", "--prompt", "fix foo.py")
    assert rc == 0
    payload = json.loads(out)
    assert payload["trivial"] is False
    assert payload["concrete_target"] is True


def test_cli_detect_relative_path() -> None:
    rc, out = _run("detect", "--prompt", "fix ./foo.py")
    assert rc == 0
    payload = json.loads(out)
    assert payload["concrete_target"] is True


def test_cli_detect_trivial() -> None:
    rc, out = _run("detect", "--prompt", "ok")
    assert rc == 0
    payload = json.loads(out)
    assert payload["trivial"] is True


def test_cli_classify_short_prompt() -> None:
    rc, out = _run("classify", "--prompt", "fix foo.py", "--mode", "rewrite")
    assert rc == 0
    payload = json.loads(out)
    assert payload["cloud_intelligence"] is False


def test_cli_target_returns_profile() -> None:
    rc, out = _run("target")
    assert rc == 0
    payload = json.loads(out)
    assert "cli" in payload
    assert "family" in payload


def test_cli_target_explicit_model_overrides_cli_family() -> None:
    rc, out = _run("target", "--cli", "codex", "--model", "MiniMax-M3")
    assert rc == 0
    payload = json.loads(out)
    assert payload["cli"] == "codex"
    assert payload["family"] == "minimax"
    assert payload["model"] == "MiniMax-M3"


def test_cmd_improve_forwards_explicit_target(monkeypatch, capsys) -> None:
    import prompt_improve.cli as cli
    import prompt_improve.command as command

    captured = {}
    monkeypatch.setenv("PROMPT_IMPROVE_TARGET_CLI", "claude")
    monkeypatch.setenv("PROMPT_IMPROVE_TARGET_MODEL", "claude-sonnet-5")

    def fake_try(prompt, mode, cwd, target):
        captured["target"] = target
        return "improved", "ollama:test", mode

    monkeypatch.setattr(command, "_try_improve", fake_try)
    args = Namespace(
        prompt="improve this integration",
        cwd=None,
        mode="rewrite",
        cli="codex",
        model="MiniMax-M3",
    )

    assert cli._cmd_improve(args) == 0
    assert json.loads(capsys.readouterr().out)["improved"] == "improved"
    assert captured["target"].cli == "codex"
    assert captured["target"].family == "minimax"


def test_cmd_target_flags_win_over_inherited_target_env(monkeypatch, capsys) -> None:
    import prompt_improve.cli as cli

    monkeypatch.setenv("PROMPT_IMPROVE_TARGET_CLI", "claude")
    monkeypatch.setenv("PROMPT_IMPROVE_TARGET_MODEL", "claude-sonnet-5")

    assert cli._cmd_target(Namespace(cli="codex", model="gpt-5.6-sol")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cli"] == "codex"
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["family"] == "openai-gpt"


def test_cli_version() -> None:
    rc, out = _run("--version")
    assert rc == 0
    assert out.startswith("prompt-improve ")


def test_cli_improve_passthrough_for_concrete_prompt() -> None:
    rc, out = _run("improve", "--prompt", "fix foo.py")
    assert rc == 0
    payload = json.loads(out)
    assert payload["status"] in {"passthrough", "trivial"}


def test_installed_command_module_dispatches_cli_subcommand() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "prompt_improve.command",
            "detect",
            "--prompt",
            "fix foo.py",
        ],
        stdin=subprocess.DEVNULL,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["concrete_target"] is True


def test_cli_improve_uses_deterministic_continuation(tmp_path: Path) -> None:
    bank = tmp_path / ".memory-bank"
    bank.mkdir()
    (bank / "currentTask.md").write_text(
        "- Active: finish deterministic CLI parity\n",
        encoding="utf-8",
    )

    rc, out = _run("improve", "--prompt", "continua", "--cwd", str(tmp_path))

    assert rc == 0
    payload = json.loads(out)
    assert payload["status"] == "improved"
    assert payload["source"] == "memory:currentTask"
    assert "deterministic CLI parity" in payload["improved"]
