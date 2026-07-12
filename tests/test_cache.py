"""Tests for prompt_improve.shared.cache: project-scoped keys, target-specific mode separation, and TTL=0 disable behavior."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from tests import compat as ip


def test_prompt_cache_key_is_project_scoped():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        (Path(a) / ".memory-bank").mkdir()
        (Path(b) / ".memory-bank").mkdir()
        assert ip._cache_key("continua", "rewrite", a) != ip._cache_key("continua", "rewrite", b)


def test_prompt_cache_key_changes_when_memory_context_changes():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        current_task = mb / "currentTask.md"
        active_context = mb / "activeContext.md"
        current_task.write_text("- Active: task A\n", encoding="utf-8")
        first = ip._cache_key("continua", "rewrite", d)

        current_task.write_text("- Active: task A with more context\n", encoding="utf-8")
        stat = current_task.stat()
        os.utime(
            current_task,
            ns=(stat.st_atime_ns + 1_000_000, stat.st_mtime_ns + 1_000_000),
        )
        second = ip._cache_key("continua", "rewrite", d)
        assert second != first

        active_context.write_text("- Active: handoff detail\n", encoding="utf-8")
        third = ip._cache_key("continua", "rewrite", d)
        assert third != second


def test_cache_mode_is_target_specific():
    import prompt_improve.features.improve as m
    from prompt_improve.features.target import profile_for_model

    claude = profile_for_model("claude-sonnet-5", "claude")
    codex = profile_for_model("gpt-5.5", "codex")
    assert m._cache_mode("rewrite", claude) != m._cache_mode("rewrite", codex)


def test_cache_ttl_zero_disables_load():
    import prompt_improve.shared.cache as cmod

    orig = cmod.CACHE_TTL_SECONDS
    cmod.CACHE_TTL_SECONDS = 0.0
    try:
        assert cmod.load_cached("test", "rewrite") is None
    finally:
        cmod.CACHE_TTL_SECONDS = orig


def test_cache_ttl_zero_disables_save():
    import prompt_improve.shared.cache as cmod

    orig = cmod.CACHE_TTL_SECONDS
    cmod.CACHE_TTL_SECONDS = 0.0
    try:
        # Should not raise even with TTL=0
        cmod.save_cached("test", "rewrite", "improved", "test")
    finally:
        cmod.CACHE_TTL_SECONDS = orig


def test_save_cached_is_atomic_and_prunes_expired(monkeypatch, tmp_path):
    import time as _time

    import prompt_improve.shared.cache as cmod

    monkeypatch.setattr(cmod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cmod, "CACHE_TTL_SECONDS", 300.0)

    expired = tmp_path / "old.json"
    expired.write_text("{}", encoding="utf-8")
    old = _time.time() - 301
    os.utime(expired, (old, old))
    stale_tmp = tmp_path / "tmpabc.tmp"
    stale_tmp.write_text("partial", encoding="utf-8")
    os.utime(stale_tmp, (old, old))

    cmod.save_cached("some prompt", "rewrite", "improved text", "ollama:x")

    assert not expired.exists(), "expired entry must be pruned on save"
    assert not stale_tmp.exists(), "stale tmp leftovers must be pruned on save"
    assert cmod.load_cached("some prompt", "rewrite") == ("improved text", "ollama:x")
    # No half-written tmp files remain after a successful save.
    assert list(tmp_path.glob("*.tmp")) == []


def test_prune_expired_keeps_fresh_entries(monkeypatch, tmp_path):
    import time as _time

    import prompt_improve.shared.cache as cmod

    monkeypatch.setattr(cmod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cmod, "CACHE_TTL_SECONDS", 300.0)

    fresh = tmp_path / "fresh.json"
    fresh.write_text("{}", encoding="utf-8")
    expired = tmp_path / "expired.json"
    expired.write_text("{}", encoding="utf-8")
    old = _time.time() - 400
    os.utime(expired, (old, old))

    removed = cmod.prune_expired()
    assert removed == 1
    assert fresh.exists()
    assert not expired.exists()


def test_load_cached_rejects_corrupt_entry(monkeypatch, tmp_path):
    """A partial/corrupt entry is a MISS and gets evicted — never a truthy (None, None)."""
    import prompt_improve.shared.cache as cmod

    monkeypatch.setattr(cmod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cmod, "CACHE_TTL_SECONDS", 300.0)

    path = cmod._cache_path(cmod._cache_key("some prompt", "rewrite", None))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"source": "ollama:x"}', encoding="utf-8")

    assert cmod.load_cached("some prompt", "rewrite") is None
    assert not path.exists(), "corrupt entry must be evicted so the next save can repopulate"
