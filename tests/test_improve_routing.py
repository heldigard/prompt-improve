"""improve cloud/local routing + shared deadline."""

from __future__ import annotations

from tests._helpers import (  # noqa: F401
    _FAKE_REWRITE,
    _load_hook,
    _patch_runner,
    _restore,
    _seq_responder,
)


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
