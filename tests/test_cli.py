"""Tests for the prompt-improve CLI (offline replay surface)."""

from __future__ import annotations

import json
import subprocess
import sys
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
