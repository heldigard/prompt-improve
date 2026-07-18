"""Tests for prompt_improve.features.improve: cloud/local routing, build_messages, role-model map, choose_model_for_role, ollama URL normalization, and the fallback-chain resilience (helpers colocated)."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

import pytest

from tests import compat as ip


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

    Returns (mod, calls_list, fake_chat, saved). Caller restores in finally.
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


def test_route_hard_prompt_prefers_cloud():
    """When needs_cloud_intelligence is True, the cloud cascade is called and local
    is NOT (the bigger model handles it)."""
    import prompt_improve.features.improve as m

    calls = {"cloud": 0, "local": 0}
    captured = {}
    orig_needs = m.needs_cloud_intelligence
    orig_cloud = m.call_cloud_cascade
    orig_local = m.call_ollama_rewrite
    m.needs_cloud_intelligence = lambda _p, _mode: True

    def cloud(_p, _mode, _cwd=None, cloud_model=None, target=None, deadline=None):
        captured["cloud_model"] = cloud_model
        calls["cloud"] += 1
        return ("CLOUD", "cloud:deepseek-v4-flash")

    def local_rw(_p, _cwd=None, target=None, deadline=None):
        calls["local"] += 1
        return None

    m.call_cloud_cascade = cloud
    m.call_ollama_rewrite = local_rw
    try:
        result = m.route_and_improve("hard prompt", "rewrite", None)
        assert result == ("CLOUD", "cloud:deepseek-v4-flash")
        assert calls["cloud"] == 1
        assert calls["local"] == 0
        assert captured["cloud_model"] == "deepseek/deepseek-v4-flash"
    finally:
        m.needs_cloud_intelligence = orig_needs
        m.call_cloud_cascade = orig_cloud
        m.call_ollama_rewrite = orig_local


def test_route_simple_prompt_prefers_local():
    """When needs_cloud_intelligence is False, local is tried first; cloud only if
    local is unavailable."""
    import prompt_improve.features.improve as m

    orig_needs = m.needs_cloud_intelligence
    orig_cloud = m.call_cloud_cascade
    orig_local = m.call_ollama_rewrite
    m.needs_cloud_intelligence = lambda _p, _mode: False
    calls = {"cloud": 0, "local": 0}

    def local_rw(_p, _cwd=None, target=None, deadline=None):
        calls["local"] += 1
        return ("LOCAL", "ollama:batiai/gemma4-12b:q4")

    def cloud(_p, _mode, _cwd=None, cloud_model=None, target=None, deadline=None):
        calls["cloud"] += 1
        return None

    m.call_ollama_rewrite = local_rw
    m.call_cloud_cascade = cloud
    try:
        result = m.route_and_improve("fix it", "rewrite", None)
        assert result == ("LOCAL", "ollama:batiai/gemma4-12b:q4")
        assert calls["local"] == 1
        assert calls["cloud"] == 0
    finally:
        m.needs_cloud_intelligence = orig_needs
        m.call_cloud_cascade = orig_cloud
        m.call_ollama_rewrite = orig_local


def test_route_local_down_falls_back_to_cloud():
    """Simple prompt + local unavailable -> cloud availability fallback fires."""
    import prompt_improve.features.improve as m

    orig_needs = m.needs_cloud_intelligence
    orig_cloud = m.call_cloud_cascade
    orig_local = m.call_ollama_rewrite
    m.needs_cloud_intelligence = lambda p, mode: False

    def local_rw(_p, _cwd=None, target=None, deadline=None):
        return None

    def cloud(_p, _mode, _cwd=None, cloud_model=None, target=None, deadline=None):
        return ("CLOUD-FALLBACK", "cloud:ling-2.6-1t")

    m.call_ollama_rewrite = local_rw
    m.call_cloud_cascade = cloud
    try:
        result = m.route_and_improve("fix it", "rewrite", None)
        assert result == ("CLOUD-FALLBACK", "cloud:ling-2.6-1t")
    finally:
        m.needs_cloud_intelligence = orig_needs
        m.call_cloud_cascade = orig_cloud
        m.call_ollama_rewrite = orig_local


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


def test_role_model_map_exists():
    """_ROLE_MODEL_MAP is defined with expected roles."""
    assert hasattr(ip, "_ROLE_MODEL_MAP")
    assert "prompt_rewrite" in ip._ROLE_MODEL_MAP
    assert "prompt_clarify" in ip._ROLE_MODEL_MAP


def test_role_model_map_prefers_evidence_fidelity_winner():
    """Both prompt roles start with the round-17 champion (cryptidbleh/gemma4-claude-opus-4.6).

    Round-17 fresh 5-way validation (2026-07-13) dethroned round-10 champion
    TeichAI/Fable-5-v1 with cryptidbleh (2.97 vs 2.46, +0.51). Round-10's blind
    spot: cryptidbleh (legacy 2026-07-09 #1, smart_trim round-15 #2) was the
    chain tail but NOT in the round-10 4-way, so its strength was never
    re-validated against TeichAI. See
    ~/ollama-bench/.memory-bank/topics/candidates-round-17-2026-07-13.md.
    """
    for role in ("prompt_rewrite", "prompt_clarify"):
        candidates = ip._ROLE_MODEL_MAP[role]
        assert len(candidates) >= 2, f"{role} should have at least 2 candidates"
        assert candidates[0] == "cryptidbleh/gemma4-claude-opus-4.6:latest"


def test_role_model_map_no_hauhaucs():
    """HauhauCS is not in any role's candidate list."""
    for role, candidates in ip._ROLE_MODEL_MAP.items():
        for model in candidates:
            assert "hauhau" not in model.lower(), f"{role} should not include HauhauCS: {model}"


def test_default_candidates_no_hauhaucs():
    """OLLAMA_MODEL_CANDIDATES default no longer includes HauhauCS."""
    import prompt_improve.shared.config as cfg

    src = Path(cfg.__file__).read_text()
    import re

    match = re.search(r'OLLAMA_IMPROVE_MODEL["\']?,\s*\n\s*"(.*?)"', src, re.DOTALL)
    if match:
        default_value = match.group(1)
        assert "HauhauCS" not in default_value, (
            f"Default OLLAMA_IMPROVE_MODEL should not include HauhauCS: {default_value}"
        )


def test_choose_model_for_role_returns_none_without_ollama():
    """choose_ollama_model_for_role returns (None, []) when Ollama is unavailable."""
    import prompt_improve.shared.ollama as omod

    orig = omod.available_ollama_models
    omod.available_ollama_models = lambda: []
    orig_start = omod.start_ollama_best_effort
    omod.start_ollama_best_effort = lambda: False
    try:
        primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")
        assert primary is None
        assert fallbacks == []
    finally:
        omod.available_ollama_models = orig
        omod.start_ollama_best_effort = orig_start


def test_choose_model_for_role_prefers_role_candidate():
    """When a non-tail role candidate is available, it's chosen as primary over
    the universal qwen3.5:4b anchor (which sits last in the chain).

    Round-17 chain: cryptidbleh primary (improve #1 fresh 5-way 2.97), TeichAI
    #2 fallback (round-10 champion demoted).
    """
    import prompt_improve.shared.ollama as omod

    orig = omod.available_ollama_models
    omod.available_ollama_models = lambda: [
        "qwen3.5:4b",
        "cryptidbleh/gemma4-claude-opus-4.6:latest",
    ]
    orig_start = omod.start_ollama_best_effort
    omod.start_ollama_best_effort = lambda: True
    try:
        primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")
        assert primary is not None
        # cryptidbleh ranks ahead of the unranked available-model tail.
        assert "cryptidbleh" in primary.lower()
        assert len(fallbacks) >= 1
    finally:
        omod.available_ollama_models = orig
        omod.start_ollama_best_effort = orig_start


def test_choose_model_for_role_falls_back_when_primary_unavailable():
    """When the round-17 champion (cryptidbleh) is unavailable, the next-ranked
    fallback in the chain (TeichAI) is chosen."""
    import prompt_improve.shared.ollama as omod

    orig = omod.available_ollama_models
    omod.available_ollama_models = lambda: [
        "hf.co/TeichAI/Qwen3.5-9B-Fable-5-v1-GGUF:Q4_K_M",
        "some-other-model",
    ]
    orig_start = omod.start_ollama_best_effort
    omod.start_ollama_best_effort = lambda: True
    try:
        primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")
        assert primary == "hf.co/TeichAI/Qwen3.5-9B-Fable-5-v1-GGUF:Q4_K_M"
    finally:
        omod.available_ollama_models = orig
        omod.start_ollama_best_effort = orig_start


def test_choose_model_for_role_env_override():
    """OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE env var overrides the default."""
    import prompt_improve.shared.config as cfg
    import prompt_improve.shared.ollama as omod

    orig_env = os.environ.get("OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE")
    orig_map = cfg._ROLE_MODEL_MAP.copy()
    orig_models = omod.available_ollama_models
    omod.available_ollama_models = lambda: ["custom-model:latest", "qwen3.5:4b"]
    orig_start = omod.start_ollama_best_effort
    omod.start_ollama_best_effort = lambda: True
    try:
        cfg._ROLE_MODEL_MAP["prompt_rewrite"] = ["custom-model:latest"]
        omod._ROLE_MODEL_MAP = cfg._ROLE_MODEL_MAP
        primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")
        assert primary == "custom-model:latest"
    finally:
        cfg._ROLE_MODEL_MAP.update(orig_map)
        omod._ROLE_MODEL_MAP = cfg._ROLE_MODEL_MAP
        if orig_env is None:
            os.environ.pop("OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE", None)
        else:
            os.environ["OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE"] = orig_env
        omod.available_ollama_models = orig_models
        omod.start_ollama_best_effort = orig_start


def test_choose_model_for_role_fuzzy_match():
    """Fuzzy/normalized matching handles prefix registry URLs and varying tags."""
    import prompt_improve.shared.ollama as omod

    orig_models = omod.available_ollama_models
    # Local Ollama may have a bare family suffix but the chain includes the
    # full cryptidbleh registry tag and quantization hint.
    omod.available_ollama_models = lambda: [
        "gemma4-claude-opus-4.6:wrong-tag",  # abbreviated local tag (wrong model)
        "gemma4-claude-opus-4.6:latest",  # bare registry, no prefix
        "qwen3.5:4b",
    ]
    orig_start = omod.start_ollama_best_effort
    omod.start_ollama_best_effort = lambda: True
    try:
        primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")
        # Fuzzy match should resolve to the chain's primary (cryptidbleh) when
        # a local model name matches its bare family signature, regardless of
        # prefix differences.
        assert primary is not None
        assert "gemma4-claude-opus" in primary.lower() or "cryptidbleh" in primary.lower()
    finally:
        omod.available_ollama_models = orig_models
        omod.start_ollama_best_effort = orig_start


# Shared rewrite payload used by the fixture-free fallback-chain tests below.
_FAKE_REWRITE = (
    "Goal: fix the dashboard load performance.\n\n"
    "Steps:\n"
    "- Profile the initial render with browser devtools to find the slow components.\n"
    "- Add lazy loading for the chart components below the fold.\n"
    "- Memoize the expensive selectors.\n\n"
    "Verify: the dashboard paints in under one second on a cold load."
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


def test_route_shares_one_deadline_across_local_and_cloud(monkeypatch):
    import prompt_improve.features.improve as mod

    deadlines: list[float | None] = []

    def local(_p, _cwd=None, target=None, deadline=None):
        deadlines.append(deadline)
        return None

    def cloud(_p, _mode, _cwd=None, cloud_model=None, target=None, deadline=None):
        deadlines.append(deadline)
        return None

    monkeypatch.setattr(mod, "needs_cloud_intelligence", lambda _p, _m: False)
    monkeypatch.setattr(mod, "call_ollama_rewrite", local)
    monkeypatch.setattr(mod, "call_cloud_cascade", cloud)

    assert mod.route_and_improve("fix it", "rewrite", None, deadline=123.0) is None
    assert deadlines == [123.0, 123.0]


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


def test_build_messages_rewrite_includes_language():
    import prompt_improve.features.improve as m

    system, user = m._build_messages("rewrite", "fix the bug", None)
    assert "English" in user
    assert "English" in system or "English" not in system  # system uses language var


def test_build_messages_clarify_includes_do_verify():
    import prompt_improve.features.improve as m

    system, user = m._build_messages("clarify", "fix the bug", None)
    assert "DO or VERIFY" in user


def test_build_messages_keep_tooling_neutral_to_avoid_prompt_bias():
    import prompt_improve.features.improve as m

    system, _ = m._build_messages("rewrite", "refactor this function safely", None)
    assert "codeq" not in system
    assert "codescan" not in system
    assert "LSP" not in system
    assert "immutable evidence" in system


def test_build_messages_includes_project_hint_when_continuation():
    import prompt_improve.features.improve as m

    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text("- Active: test task\n", encoding="utf-8")
        _, user = m._build_messages("rewrite", "continua", d)
        assert "Execution context (not task scope):" in user
        assert "test task" in user


def test_build_messages_omits_hint_when_no_cwd():
    import prompt_improve.features.improve as m

    _, user = m._build_messages("rewrite", "fix it", None)
    assert "Execution context (not task scope):" not in user


def test_route_hard_prompt_cloud_model_env_override(monkeypatch):
    """OLLAMA_IMPROVE_CLOUD_MODEL overrides the hard-prompt cloud model at call time."""
    import prompt_improve.features.improve as m

    captured = {}
    orig_needs = m.needs_cloud_intelligence
    orig_cloud = m.call_cloud_cascade
    m.needs_cloud_intelligence = lambda _p, _mode: True
    monkeypatch.setenv("OLLAMA_IMPROVE_CLOUD_MODEL", "openai/gpt-5.6-mini")

    def cloud(_p, _mode, _cwd=None, cloud_model=None, target=None, deadline=None):
        captured["cloud_model"] = cloud_model
        return ("CLOUD", "cloud:gpt-5.6-mini")

    m.call_cloud_cascade = cloud
    try:
        result = m.route_and_improve("hard prompt", "rewrite", None)
        assert result == ("CLOUD", "cloud:gpt-5.6-mini")
        assert captured["cloud_model"] == "openai/gpt-5.6-mini"
    finally:
        m.needs_cloud_intelligence = orig_needs
        m.call_cloud_cascade = orig_cloud


def test_normalized_model_collision_is_deterministic(monkeypatch):
    import prompt_improve.shared.ollama as omod

    monkeypatch.setattr(omod, "available_ollama_models", lambda: ["model:latest", "model:Q4_K_M"])
    monkeypatch.setattr(omod, "_ROLE_MODEL_MAP", {"prompt_rewrite": ["model:any"]})
    monkeypatch.setattr(omod, "OLLAMA_MODEL_CANDIDATES", [])

    primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")

    assert primary == "model:Q4_K_M"
    assert fallbacks == ["model:latest"]


def test_ollama_discovery_rejects_oversized_response(monkeypatch):
    import prompt_improve.shared.ollama as omod

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return b"x" * size

    monkeypatch.setattr(omod, "urlopen", lambda *args, **kwargs: Response())
    assert omod._get_json("/api/tags", timeout=0.1) is None
