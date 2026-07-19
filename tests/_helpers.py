"""Shared improve-feature test helpers (extracted from the former test_improve monolith)."""

from __future__ import annotations

import importlib.util  # noqa: F401
import os  # noqa: F401
import sys  # noqa: F401
import tempfile  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any, cast  # noqa: F401


def _load_hook():
    """Load a fresh instance of the improve module for monkeypatching."""
    import prompt_improve.features.improve as mod

    importlib.reload(mod)
    return mod


def _seq_responder(seq):
    """Build a callable yielding items from ``seq`` in order. Strings are
    returned as chat content; BaseException instances are RAISED (so a model
    that fails to load or is unreachable can be expressed in the same sequence
    as a model that returns content)."""
    it = iter(seq)

    def _respond():
        item = next(it)
        if isinstance(item, BaseException):
            raise item
        return item

    return _respond


def _patch_runner():
    """Install a fake ollama_client + controlled model picker on the loaded module.

    Returns ``(mod, calls, saved, ReqErr, Unavail, fake_chat)``.
    Caller restores via ``_restore(mod, saved)`` in ``finally``.
    """
    import types

    mod = _load_hook()

    # Stand-in exception classes — the except clauses match by object identity,
    # so these need not be the real ollama_client classes (keeps the test offline
    # and independent of whether the daemon/scripts are present).
    class _ReqErr(Exception):
        pass

    class _Unavail(Exception):
        pass

    calls: list[str] = []

    def fake_chat(messages, **kw):  # noqa: ANN001
        calls.append(kw.get("model") or "")
        return fake_chat._next()  # type: ignore[attr-defined]

    fake_oc = types.SimpleNamespace(
        chat=fake_chat,
        OllamaRequestError=_ReqErr,
        OllamaUnavailable=_Unavail,
    )

    saved = {
        "oc": mod.compat.ollama_client,
        "pick": mod.choose_ollama_model_for_role,
        "load": mod.load_cached,
        "save": mod.save_cached,
    }
    mod.compat.ollama_client = fake_oc
    mod.choose_ollama_model_for_role = lambda role: ("primary_model", ["fallback_model"])
    mod.load_cached = lambda *a, **k: None
    mod.save_cached = lambda *a, **k: None
    return mod, calls, saved, _ReqErr, _Unavail, fake_chat


def _restore(mod, saved):
    mod.compat.ollama_client = saved["oc"]
    mod.choose_ollama_model_for_role = saved["pick"]
    mod.load_cached = saved["load"]
    mod.save_cached = saved["save"]


_FAKE_REWRITE = (
    "Goal: fix the dashboard load performance.\n\n"
    "Steps:\n"
    "- Profile the initial render with browser devtools to find the slow components.\n"
    "- Add lazy loading for the chart components below the fold.\n"
    "- Memoize the expensive selectors.\n\n"
    "Verify: the dashboard paints in under one second on a cold load."
)
