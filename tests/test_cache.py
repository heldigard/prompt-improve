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
