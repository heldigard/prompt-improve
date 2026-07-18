"""Tests for prompt_improve.shared.metrics: record/emit gating, reset, and
end-to-end emission from the hook entry point."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
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


def test_metrics_persists_jsonl_when_enabled(tmp_path, monkeypatch) -> None:
    """When OLLAMA_IMPROVE_METRICS_PERSIST=1, emit writes metrics.jsonl."""
    monkeypatch.setenv("OLLAMA_IMPROVE_METRICS_PERSIST", "1")
    monkeypatch.setenv("OLLAMA_IMPROVE_METRICS_DIR", str(tmp_path))
    from prompt_improve.shared import metrics

    metrics._counts.clear()
    metrics.record("ollama")
    metrics.record("cache:hit")
    metrics.emit()
    target = tmp_path / "metrics.jsonl"
    assert target.exists()
    line = target.read_text().strip()
    assert "ollama" in line and "cache:hit" in line
    rec = json.loads(line)
    assert rec["counts"]["ollama"] == 1


def test_metrics_busy_lock_skips_optional_persistence(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_IMPROVE_METRICS_PERSIST", "1")
    monkeypatch.setenv("OLLAMA_IMPROVE_METRICS_DIR", str(tmp_path))
    from prompt_improve.shared import metrics

    @contextmanager
    def busy_lock(_handle):
        yield False

    monkeypatch.setattr(metrics.filelock, "try_exclusive_lock", busy_lock)
    metrics._counts.clear()
    metrics.record("ollama")

    metrics.emit()

    target = tmp_path / "metrics.jsonl"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == ""


def test_metrics_silent_when_disabled(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("OLLAMA_IMPROVE_METRICS", raising=False)
    monkeypatch.delenv("OLLAMA_IMPROVE_METRICS_PERSIST", raising=False)
    monkeypatch.delenv("OLLAMA_IMPROVE_DEBUG", raising=False)
    from prompt_improve.shared import metrics

    metrics._counts.clear()
    metrics.record("ollama")
    metrics.emit()
    assert not (tmp_path / "metrics.jsonl").exists()
