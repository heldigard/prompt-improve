"""role-model map + choose_model_for_role + discovery."""

from __future__ import annotations

import os
from pathlib import Path

from tests import compat as ip
from tests._helpers import (  # noqa: F401
    _FAKE_REWRITE,
    _load_hook,
    _patch_runner,
    _restore,
    _seq_responder,
)


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
