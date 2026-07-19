"""cloud-cascade postprocess / timeout / programmer errors."""

from __future__ import annotations

import os
import sys
from typing import Any, cast

import pytest

from tests._helpers import (  # noqa: F401
    _FAKE_REWRITE,
    _load_hook,
    _patch_runner,
    _restore,
    _seq_responder,
)


def test_cloud_cascade_env_opt_out():
    """OLLAMA_IMPROVE_CLOUD_FALLBACK=0 must short-circuit to None (no cloud call)."""
    import prompt_improve.features.improve as imod
    import prompt_improve.shared.config as cfg

    orig = cfg.CLOUD_FALLBACK
    cfg.CLOUD_FALLBACK = False
    imod.CLOUD_FALLBACK = False
    try:
        assert imod.call_cloud_cascade("fix the bug", "rewrite") is None
    finally:
        cfg.CLOUD_FALLBACK = orig
        imod.CLOUD_FALLBACK = orig


def test_cloud_cascade_postprocesses_output():
    """Cloud output runs through the SAME _clean pipeline: invented absolutes softened,
    'Preguntas de validación' stripped, source labeled cloud:<model>."""
    import types as _types

    import prompt_improve.features.improve as imod
    import prompt_improve.shared.config as cfg

    stub = _types.ModuleType("cheap_llm")

    def fake_complete(**_):
        return {
            "text": (
                "Fix the bug.\n\nAcceptance criteria: 100% coverage.\n\n"
                "Preguntas de validación:\n1. which file?"
            ),
            "model": "ling-2.6-flash",
            "tier": "T2",
        }

    cast(Any, stub).cheap_complete = fake_complete
    cfg.CLOUD_FALLBACK = True
    imod.CLOUD_FALLBACK = True
    old_compat = imod.compat.cheap_complete
    imod.compat.cheap_complete = fake_complete
    old_mod = sys.modules.get("cheap_llm")
    sys.modules["cheap_llm"] = stub
    try:
        result = imod.call_cloud_cascade("fix the bug", "rewrite")
    finally:
        imod.compat.cheap_complete = old_compat
        if old_mod is None:
            sys.modules.pop("cheap_llm", None)
        else:
            sys.modules["cheap_llm"] = old_mod
    assert result is not None, "cloud cascade should return a result with the stub"
    text, src = result
    assert src == "cloud:ling-2.6-flash"
    assert "100% coverage" not in text
    assert "Preguntas de validación" not in text
    assert "which file?" not in text


def test_cloud_cascade_clamps_timeout_to_shared_deadline(monkeypatch):
    import prompt_improve.features.improve as mod

    captured: dict[str, float] = {}

    def fake_complete(**kwargs):
        captured["timeout_total"] = kwargs["timeout_total"]
        return {
            "text": "Task: Fix the bug.\nAcceptance criteria: run the focused tests.",
            "model": "cloud-test",
        }

    monkeypatch.setattr(mod.compat, "cheap_complete", fake_complete)
    monkeypatch.setattr(mod, "CLOUD_FALLBACK", True)
    monkeypatch.setattr(mod, "monotonic", lambda: 100.0)

    result = mod.call_cloud_cascade("fix the bug", "rewrite", deadline=104.0)

    assert result is not None
    assert captured["timeout_total"] == 4.0


def test_cloud_cascade_does_not_swallow_programmer_errors():
    """Regression 2026-07-04: narrow exception list must NOT catch NameError /
    AttributeError. Those are programmer bugs that should surface, not silently
    fall through to the rule-based fallback."""
    import prompt_improve.features.improve as imod
    import prompt_improve.shared.config as cfg

    def boom(**_):
        raise NameError("cheap_llm misconfigured — NOT a transient failure")

    cfg.CLOUD_FALLBACK = True
    imod.CLOUD_FALLBACK = True
    old = imod.compat.cheap_complete
    imod.compat.cheap_complete = boom
    try:
        with __import__("pytest").raises(NameError):
            imod.call_cloud_cascade("fix the bug", "rewrite")
    finally:
        imod.compat.cheap_complete = old


def test_smoke_cloud_cascade_live():
    """Live cloud cascade smoke. Skipped without cheap_llm or OPENROUTER_API_KEY."""
    import prompt_improve.features.improve as imod

    try:
        import cheap_llm  # type: ignore[import-not-found]  # noqa: F401
    except Exception:
        pytest.skip("cheap_llm not importable")
    if not os.environ.get("OPENROUTER_API_KEY"):
        pytest.skip("no OPENROUTER_API_KEY")
    result = imod.call_cloud_cascade("fix the bug", "rewrite")
    if result is None:
        pytest.skip("cloud cascade unavailable")
    text, src = result
    assert src.startswith("cloud:")
    assert "Contexto:" not in text
    assert "Preguntas de validación" not in text
