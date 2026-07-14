"""Tests for prompt_improve.shared.metrics: record/emit gating, reset, and
end-to-end emission from the hook entry point."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def test_record_and_emit_when_enabled(capsys, monkeypatch):
    import prompt_improve.shared.metrics as m

    monkeypatch.setenv("OLLAMA_IMPROVE_METRICS", "1")
    m._counts.clear()
    m.record("cache:hit")
    m.record("cache:hit")
    m.record("ollama")
    m.emit()
    err = capsys.readouterr().err
    assert "[prompt-improve metrics]" in err
    assert "cache:hit=2" in err
    assert "ollama=1" in err
    # reset cleared the counters after emitting
    assert dict(m._counts) == {}


def test_emit_silent_when_disabled(capsys, monkeypatch):
    """No stderr output when neither METRICS nor DEBUG is set; counts survive."""
    import prompt_improve.shared.metrics as m

    monkeypatch.delenv("OLLAMA_IMPROVE_METRICS", raising=False)
    monkeypatch.delenv("OLLAMA_IMPROVE_DEBUG", raising=False)
    m._counts.clear()
    m.record("ollama")
    m.emit()
    assert capsys.readouterr().err == ""
    assert m._counts["ollama"] == 1


def test_emit_also_fires_under_debug(capsys, monkeypatch):
    import prompt_improve.shared.metrics as m

    monkeypatch.delenv("OLLAMA_IMPROVE_METRICS", raising=False)
    monkeypatch.setenv("OLLAMA_IMPROVE_DEBUG", "1")
    m._counts.clear()
    m.record("cloud")
    m.emit()
    assert "cloud=1" in capsys.readouterr().err


def test_emit_noop_when_empty(capsys, monkeypatch):
    import prompt_improve.shared.metrics as m

    monkeypatch.setenv("OLLAMA_IMPROVE_METRICS", "1")
    m._counts.clear()
    m.emit()
    assert capsys.readouterr().err == ""


def test_hook_emits_metrics_line_for_trivial_prompt():
    """End-to-end: a trivial prompt records passthrough:trivial and the hook
    prints the metrics line to stderr when OLLAMA_IMPROVE_METRICS=1."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["OLLAMA_IMPROVE_METRICS"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "prompt_improve.command"],
        input=json.dumps({"prompt": "ok"}),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"continue": True}
    assert "[prompt-improve metrics]" in result.stderr
    assert "passthrough:trivial=1" in result.stderr
