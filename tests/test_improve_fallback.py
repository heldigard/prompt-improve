"""fallback-chain resilience across failures."""

from __future__ import annotations

from typing import Any, cast

from tests._helpers import (  # noqa: F401
    _FAKE_REWRITE,
    _load_hook,
    _patch_runner,
    _restore,
    _seq_responder,
)


def test_fallback_chain_continues_past_model_load_failure():
    """Primary raises OllamaRequestError (HTTP 500 / VRAM load failure) → the
    chain MUST advance to the fallback and succeed, not abort."""
    mod, calls, saved, ReqErr, _Unavail, fake_chat = _patch_runner()
    cast(Any, fake_chat)._next = _seq_responder(
        [ReqErr("HTTP 500: unable to load model"), _FAKE_REWRITE]
    )
    try:
        result = mod.call_ollama_rewrite("haz el dashboard mas rapido", cwd=None)
    finally:
        _restore(mod, saved)
    # Both models were attempted (primary failed, fallback succeeded)
    assert calls == ["primary_model", "fallback_model"], f"chain aborted early: {calls}"
    assert result is not None, "fallback produced no result"
    text, source = result
    assert source == "ollama:fallback_model"
    assert "dashboard" in text.lower()


def test_fallback_chain_aborts_on_daemon_down():
    """OllamaUnavailable (daemon unreachable) → abort the whole chain; do NOT
    burn time trying further models against a down daemon."""
    mod, calls, saved, _ReqErr, Unavail, fake_chat = _patch_runner()
    cast(Any, fake_chat)._next = _seq_responder([Unavail("connection refused")])
    try:
        result = mod.call_ollama_rewrite("haz el dashboard mas rapido", cwd=None)
    finally:
        _restore(mod, saved)
    assert result is None, "daemon-down should yield None, not a fallback attempt"
    # Only the primary was tried — the chain aborted immediately
    assert calls == ["primary_model"], f"chain did not abort on daemon-down: {calls}"


def test_fallback_chain_skips_empty_then_succeeds():
    """A model that returns empty (think-leak / no content) is skipped via
    `if not content: continue` — distinct from a load failure."""
    mod, calls, saved, _ReqErr, _Unavail, fake_chat = _patch_runner()
    cast(Any, fake_chat)._next = _seq_responder(["", "   ", _FAKE_REWRITE])
    cast(Any, mod).choose_ollama_model_for_role = lambda role: (
        "primary_model",
        ["second_model", "third_model"],
    )
    try:
        result = mod.call_ollama_rewrite("haz el dashboard mas rapido", cwd=None)
    finally:
        _restore(mod, saved)
    assert result is not None
    _, source = result
    assert source == "ollama:third_model", f"empty models should be skipped: {source}"
    assert calls == ["primary_model", "second_model", "third_model"]


def test_fallback_chain_respects_total_latency_budget():
    """A slow primary must not grant every fallback another full timeout."""
    mod, calls, saved, ReqErr, _Unavail, fake_chat = _patch_runner()
    cast(Any, fake_chat)._next = _seq_responder([ReqErr("primary timed out")])
    old_monotonic = mod.monotonic
    old_budget = mod.OLLAMA_TOTAL_TIMEOUT
    timestamps = iter((100.0, 100.0, 125.0))
    cast(Any, mod).monotonic = lambda: next(timestamps)
    cast(Any, mod).OLLAMA_TOTAL_TIMEOUT = 24.0
    try:
        result = mod.call_ollama_rewrite("haz el dashboard mas rapido", cwd=None)
    finally:
        cast(Any, mod).monotonic = old_monotonic
        cast(Any, mod).OLLAMA_TOTAL_TIMEOUT = old_budget
        _restore(mod, saved)
    assert result is None
    assert calls == ["primary_model"]


def test_unexpected_ollama_client_error_falls_through():
    mod, calls, saved, _ReqErr, _Unavail, fake_chat = _patch_runner()
    cast(Any, fake_chat)._next = _seq_responder([RuntimeError("response parser drift")])
    try:
        result = mod.call_ollama_rewrite("haz el dashboard mas rapido", cwd=None)
    finally:
        _restore(mod, saved)

    assert result is None
    assert calls == ["primary_model"]
