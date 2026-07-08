"""Tests for prompt_improve.features.classify: decide_mode threshold/override and needs_cloud hard-domain detection."""

from __future__ import annotations

import os

from tests import compat as ip


def test_decide_mode_threshold():
    # Force "auto" mode
    os.environ.pop("OLLAMA_IMPROVE_MODE", None)
    assert ip.decide_mode("fix it") == "rewrite"  # short
    assert ip.decide_mode("x" * ip.REWRITE_THRESHOLD) == "clarify"  # long


def test_decide_mode_explicit_override():
    os.environ["OLLAMA_IMPROVE_MODE"] = "clarify"
    try:
        assert ip.decide_mode("fix it") == "clarify"
    finally:
        os.environ.pop("OLLAMA_IMPROVE_MODE", None)


def test_needs_cloud_hard_domains():
    """Prompts in hard domains (security/concurrency/distributed/architecture/
    migration/regex/algorithm/refactor-for-scale) must escalate to the cloud model."""
    hard = [
        "review our auth flow for security vulnerabilities",
        "fix the race condition in the transaction handler",
        "design a distributed consensus for the migration with zero downtime",
        "audit the regex for injection and optimize the algorithmic complexity",
        "refactor the monolith into microservices and make it scalable",
        "analiza la seguridad del OAuth y la concurrencia de la transaccion",
        "revisa la configuracion cross-cli del prompt improver, smart-trim, subagentes y fusion",
        "improve the agentic orchestration for memory-bank compaction and OpenRouter Fusion",
    ]
    for p in hard:
        assert ip.needs_cloud_intelligence(p, "clarify") is True, f"should escalate: {p!r}"


def test_needs_cloud_simple_stays_local():
    """Simple prompts the local model handles well must NOT escalate."""
    simple = [
        "fix the bug",
        "add tests",
        "review the PR",
        "update the docs",
        "explain the function",
        "fix the bug in src/app.py",
        "mejora el rendimiento",
    ]
    for p in simple:
        assert ip.needs_cloud_intelligence(p, "rewrite") is False, f"should stay local: {p!r}"


def test_needs_cloud_env_disable():
    os.environ["OLLAMA_IMPROVE_CLOUD_INTELLIGENCE"] = "0"
    try:
        hard = "audit security and refactor for scalability with distributed consensus"
        assert ip.needs_cloud_intelligence(hard, "clarify") is False
    finally:
        os.environ.pop("OLLAMA_IMPROVE_CLOUD_INTELLIGENCE", None)
