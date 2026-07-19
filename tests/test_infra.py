"""Tests for package infrastructure: import surface stability, the eval fixture, live ollama smoke (skipped when no daemon), debug logging, and ollama-serve launch guard."""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

from tests import compat as ip

EVALS = Path(__file__).resolve().parent.parent / "evals" / "prompt-improve.json"
CANONICAL_SHIM = Path(__file__).resolve().parent.parent / "prompt-improve.py"
LIVE_SHIM = Path.home() / ".claude" / "hooks" / "prompt-improve.py"


def _ollama_available() -> bool:
    try:
        return bool(ip.available_ollama_models())
    except Exception:
        return False


def test_eval_fixture_properties():
    """Consume evals/prompt-improve.json and assert each declared property."""
    if not EVALS.exists():
        return  # no fixtures → nothing to assert
    data = json.loads(EVALS.read_text(encoding="utf-8"))
    for case in data.get("cases", []):
        cid = case.get("id", "?")
        prompt = case["prompt"]
        if "expect_trivial" in case:
            assert ip.detect_trivial(prompt) is case["expect_trivial"], f"[{cid}] trivial mismatch"
        if case.get("expect_concrete_target") is not None:
            assert ip.has_concrete_target(prompt) is case["expect_concrete_target"], (
                f"[{cid}] concrete mismatch"
            )
        if "expect_language" in case:
            assert ip.detect_language(prompt) == case["expect_language"], (
                f"[{cid}] language mismatch"
            )


def test_smoke_rewrite_no_es_leak_no_question_loop():
    """End-to-end: a real rewrite of an English prompt must not leak Spanish
    section headers, must not end with validation questions, and must not
    invent '100% coverage'. Skipped when ollama is unavailable."""
    import prompt_improve.shared.cache as cache_mod

    if not _ollama_available():
        pytest.skip("ollama not available")
    orig_ttl = cache_mod.CACHE_TTL_SECONDS
    cache_mod.CACHE_TTL_SECONDS = 0.0
    try:
        result = ip.call_ollama_rewrite("fix the bug")
    finally:
        cache_mod.CACHE_TTL_SECONDS = orig_ttl
    if result is None:
        pytest.skip("ollama returned no output")
    text = result[0]
    assert "Contexto:" not in text and "Objetivo:" not in text
    assert "Preguntas de validación" not in text.lower()
    assert "validation questions" not in text.lower()
    assert "100% coverage" not in text.lower()


def test_package_import_surface_stable():
    """The refactor preserved the public import path consumed by rules/improve."""
    from prompt_improve.features.target import (  # noqa: I001
        GENERIC_TARGET,
        TargetProfile,
        profile_for_model,
        target_guidance,
        target_profile_from_request,
    )

    assert GENERIC_TARGET.family == "generic"
    assert isinstance(TargetProfile, type)
    assert callable(profile_for_model)
    assert callable(target_guidance)
    assert callable(target_profile_from_request)


def test_live_shim_matches_tracked_source():
    """The wired shim must not drift from the repository source of truth."""
    if not LIVE_SHIM.exists():
        pytest.skip("live Claude shim is absent in CI")
    assert LIVE_SHIM.read_bytes() == CANONICAL_SHIM.read_bytes()


def test_launch_ollama_serve_returns_none_when_log_dir_fails():
    import prompt_improve.shared.ollama as omod

    orig_log = omod.OLLAMA_LOG
    omod.OLLAMA_LOG = "/nonexistent/dir/ollama.log"
    try:
        result = omod._launch_ollama_serve()
        assert result is None
    finally:
        omod.OLLAMA_LOG = orig_log


def test_spawn_ollama_prefers_systemd_when_available(monkeypatch):
    import prompt_improve.shared.ollama as omod

    monkeypatch.setattr(omod.shutil, "which", lambda name: "/usr/bin/systemctl")
    calls = []

    class _Result:
        returncode = 0

    def _run(cmd, **kwargs):
        calls.append(cmd)
        return _Result()

    monkeypatch.setattr(omod.subprocess, "run", _run)
    monkeypatch.setattr(
        omod, "_launch_ollama_serve", lambda: pytest.fail("nohup fallback must not run")
    )
    assert omod._spawn_ollama() is True
    assert calls[0] == ["systemctl", "--user", "cat", "ollama.service"]
    assert calls[1] == ["systemctl", "--user", "start", "ollama"]


def test_spawn_ollama_falls_back_to_nohup_without_systemd(monkeypatch):
    import prompt_improve.shared.ollama as omod

    monkeypatch.setattr(omod.shutil, "which", lambda name: None)

    class _Proc:
        pid = 4242

    monkeypatch.setattr(omod, "_launch_ollama_serve", lambda: _Proc())
    monkeypatch.setattr(omod, "OLLAMA_PID", "/tmp/prompt-improve-test-ollama.pid")
    try:
        assert omod._spawn_ollama() is True
    finally:
        os.unlink("/tmp/prompt-improve-test-ollama.pid")


def test_systemctl_start_returns_false_when_unit_missing(monkeypatch):
    import prompt_improve.shared.ollama as omod

    monkeypatch.setattr(omod.shutil, "which", lambda name: "/usr/bin/systemctl")

    class _Result:
        returncode = 1

    monkeypatch.setattr(omod.subprocess, "run", lambda cmd, **kwargs: _Result())
    assert omod._systemctl_start_ollama() is False


def test_is_chat_model_filters_embedding_tags():
    import prompt_improve.shared.ollama as omod

    assert omod._is_chat_model("cryptidbleh/gemma4-claude-opus-4.6:latest") is True
    assert omod._is_chat_model("hf.co/TeichAI/Qwen3.5-9B-Fable-5-v1-GGUF:Q4_K_M") is True
    assert omod._is_chat_model("nomic-embed-text:latest") is False
    assert omod._is_chat_model("bge-m3:latest") is False
    assert omod._is_chat_model("embeddinggemma:latest") is False
    assert omod._is_chat_model("") is False


def test_choose_ollama_model_skips_embedding_tail(monkeypatch):
    """When only embeddings remain after the preferred chain, return empty rather
    than burning the hook budget on a non-chat model."""
    import prompt_improve.shared.ollama as omod

    monkeypatch.setattr(
        omod,
        "available_ollama_models",
        lambda: ["nomic-embed-text:latest", "bge-m3:latest", "embeddinggemma:latest"],
    )
    monkeypatch.setattr(omod, "OLLAMA_MODEL_CANDIDATES", ["missing-chat:latest"])
    monkeypatch.setattr(omod, "_ROLE_MODEL_MAP", {"prompt_rewrite": ["missing-chat:latest"]})
    primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")
    assert primary is None
    assert fallbacks == []


def test_choose_ollama_model_keeps_chat_tail(monkeypatch):
    import prompt_improve.shared.ollama as omod

    monkeypatch.setattr(
        omod,
        "available_ollama_models",
        lambda: [
            "nomic-embed-text:latest",
            "cryptidbleh/gemma4-claude-opus-4.6:latest",
            "bge-m3:latest",
        ],
    )
    monkeypatch.setattr(omod, "OLLAMA_MODEL_CANDIDATES", ["missing-preferred:latest"])
    monkeypatch.setattr(omod, "_ROLE_MODEL_MAP", {"prompt_rewrite": ["missing-preferred:latest"]})
    primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")
    assert primary == "cryptidbleh/gemma4-claude-opus-4.6:latest"
    assert "nomic-embed-text:latest" not in fallbacks
    assert "bge-m3:latest" not in fallbacks


def test_debug_noop_when_disabled():
    import prompt_improve.features.improve as m

    orig = m._DEBUG
    m._DEBUG = False
    try:
        # Should not raise or produce output
        m._debug("test message")
    finally:
        m._DEBUG = orig


def test_debug_writes_to_stderr_when_enabled():
    import prompt_improve.features.improve as m

    orig = m._DEBUG
    m._DEBUG = True
    captured = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = captured
    try:
        m._debug("test message")
    finally:
        sys.stderr = old_stderr
        m._DEBUG = orig
    assert "test message" in captured.getvalue()
