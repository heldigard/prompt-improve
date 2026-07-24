"""improve cloud/local routing + shared deadline."""

from __future__ import annotations

from tests._helpers import (  # noqa: F401
    _FAKE_REWRITE,
    _load_hook,
    _patch_runner,
    _restore,
    _seq_responder,
)


def test_route_hard_prompt_prefers_cloud(monkeypatch):
    """When needs_cloud_intelligence is True, the cloud cascade is called and local
    is NOT (the bigger model handles it)."""
    import prompt_improve.features.improve as m

    calls = {"cloud": 0, "local": 0}
    captured = {}
    orig_needs = m.needs_cloud_intelligence
    orig_cloud = m.call_cloud_cascade
    orig_local = m.call_ollama_rewrite
    m.needs_cloud_intelligence = lambda _p, _mode: True
    monkeypatch.setattr(m, "load_cached", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(m, "save_cached", lambda *_args, **_kwargs: None)

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
    monkeypatch.setattr(m, "load_cached", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(m, "save_cached", lambda *_args, **_kwargs: None)

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


def test_route_hard_prompt_caches_successful_cloud_result(monkeypatch, tmp_path):
    """Cloud-first routing must share the normal target/mode cache.

    Without this route-level save, repeated hard prompts always paid for a new
    cloud call because only the local-first helpers owned cache persistence.
    """
    import prompt_improve.features.improve as m
    import prompt_improve.shared.cache as cache_mod

    (tmp_path / ".memory-bank").mkdir()
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(cache_mod, "CACHE_TTL_SECONDS", 300.0)
    monkeypatch.setattr(m, "needs_cloud_intelligence", lambda _p, _mode: True)
    calls = 0

    def cloud(_p, _mode, _cwd=None, cloud_model=None, target=None, deadline=None):
        nonlocal calls
        calls += 1
        return ("CLOUD-CACHED", "cloud:deepseek-v4-flash")

    monkeypatch.setattr(m, "call_cloud_cascade", cloud)
    monkeypatch.setattr(
        m,
        "call_ollama_rewrite",
        lambda *_args, **_kwargs: __import__("pytest").fail("local must not run"),
    )

    kwargs = {
        "prompt": "audit this architecture for security risks",
        "mode": "rewrite",
        "cwd": str(tmp_path),
        "target": m.GENERIC_TARGET,
    }
    assert m.route_and_improve(**kwargs) == (
        "CLOUD-CACHED",
        "cloud:deepseek-v4-flash",
    )
    assert m.route_and_improve(**kwargs) == (
        "CLOUD-CACHED",
        "cloud:deepseek-v4-flash",
    )
    assert calls == 1


def test_route_cloud_opt_out_does_not_reuse_cloud_cache(monkeypatch):
    """Disabling cloud must also ignore a previously persisted cloud result."""
    import prompt_improve.features.improve as m

    monkeypatch.setattr(m, "needs_cloud_intelligence", lambda _p, _mode: True)
    monkeypatch.setattr(m, "CLOUD_FALLBACK", False)
    monkeypatch.setattr(
        m,
        "load_cached",
        lambda *_args, **_kwargs: __import__("pytest").fail(
            "cloud cache must not be read while cloud is disabled"
        ),
    )
    monkeypatch.setattr(m, "call_cloud_cascade", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        m,
        "call_ollama_rewrite",
        lambda *_args, **_kwargs: ("LOCAL", "ollama:test"),
    )

    assert m.route_and_improve(
        "audit this architecture for security risks",
        "rewrite",
        None,
        target=m.GENERIC_TARGET,
    ) == ("LOCAL", "ollama:test")
