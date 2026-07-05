#!/usr/bin/env python3
"""
Regression tests for prompt-improve package.

Covers the 2026-06-25 fixes:
  P0  detect_trivial no longer silences real short task prompts (was 11/15 false-trivial).
  P1  rewrite section labels match the user's language (no ES headers on EN prompts).
  P2  invented absolute targets ("100% coverage") are softened; rewrite is not truncated.
  P3  output is agent-oriented (no "Preguntas de validación" question-loop).
  P4  project hint is extracted from cwd + nearest .memory-bank/currentTask.md.
  Fast-path: a short prompt naming a concrete file + verb skips rewrite.

Pure-function tests run offline. The ollama smoke test is skipped when no daemon
is reachable. Run: `python3 -m pytest tests/ -q`
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

# Import the compat shim that re-exports all symbols from the package
from tests import compat as ip

EVALS = Path(__file__).resolve().parent.parent / "evals" / "prompt-improve.json"


def _load_hook():
    """Load a fresh instance of the improve module for monkeypatching."""
    import prompt_improve.features.improve as mod

    importlib.reload(mod)
    return mod


# ---- P0: detect_trivial ----------------------------------------------------

TRIVIAL_TRUE = [
    "",
    "ok",
    "ok thanks",
    "vale listo",
    "got it",
    "yes",
    "no",
    "yep",
    "hi",
    "hello",
    "hola",
    "hey",
    "bye",
    "chao",
    "/commit",
    "/review",
    "/compact",
    "/status",
    "a",
    "ab",
]

# Real short task prompts that MUST NOT be silenced (the 2026-06-25 bug set + more).
TRIVIAL_FALSE = [
    "debug the auth",
    "review the PR",
    "explain the function",
    "show me the code",
    "write a test",
    "update the docs",
    "optimize this loop",
    "find the bug",
    "add logging",
    "document the API",
    "read the config",
    "clean it up",
    "explica esto",
    "revisa el login",
    "fix it",
    "fix the bug",
    "mejora el rendimiento",
    "add tests",
    "genera el reporte",
    "valida el input",
    "migrate the db",
    "lint the project",
    "profile this route",
    "scan for secrets",
    "continua",
    "continua por favor",
    "continue where you left off",
]


def test_detect_trivial_acknowledgments_and_greetings():
    for p in TRIVIAL_TRUE:
        assert ip.detect_trivial(p) is True, f"should be trivial: {p!r}"


def test_detect_trivial_real_tasks_not_silenced():
    failures = [p for p in TRIVIAL_FALSE if ip.detect_trivial(p) is True]
    assert not failures, f"false-trivial (silenced real tasks): {failures}"


# ---- P1: language-aware rewrite labels -------------------------------------


def test_rewrite_prompt_english_labels():
    prompt = ip.build_rewrite_system_prompt("English")
    for label in ("Task", "Context", "Objective", "Constraints", "Acceptance criteria"):
        assert label in prompt
    # No Spanish header leak
    for es in ("Contexto:", "Objetivo:", "Restricciones:", "Criterios de aceptación:"):
        assert es not in prompt


def test_rewrite_prompt_spanish_labels():
    prompt = ip.build_rewrite_system_prompt("Spanish")
    for label in ("Tarea", "Contexto", "Objetivo", "Restricciones", "Criterios de aceptación"):
        assert label in prompt


def test_detect_language_matches_unaccented_spanish_markers():
    # Bug fix 2026-07-04: prompt.lower() preserves accents, so a user typing
    # "que" or "configuracion" (no accent) was missed by the old marker list.
    assert ip.detect_language("que quieres hacer") == "Spanish"
    assert ip.detect_language("configuracion del proyecto") == "Spanish"
    # Sanity: accented variants still match.
    assert ip.detect_language("qué quieres hacer") == "Spanish"
    assert ip.detect_language("configuración del proyecto") == "Spanish"
    # English stays English.
    assert ip.detect_language("what do you want to do") == "English"


def test_rewrite_prompt_forbids_user_questions_and_absolutes():
    en = ip.build_rewrite_system_prompt("English")
    es = ip.build_rewrite_system_prompt("Spanish")
    assert "questions for the user" in en.lower()
    assert "100% coverage" in en
    assert "100% cobertura" in es


# ---- P2: soften invented absolutes -----------------------------------------


def test_soften_absolutes_english():
    assert "100% coverage" not in ip._soften_invented_absolutes("Ensure 100% coverage")
    assert "zero downtime" not in ip._soften_invented_absolutes("zero downtime guaranteed")
    assert "broad test coverage" in ip._soften_invented_absolutes("Require full test coverage")


def test_soften_absolutes_spanish():
    out = ip._soften_invented_absolutes("Garantizar 100% de cobertura y cobertura total")
    assert "100% de cobertura" not in out
    assert "cobertura total" not in out


# ---- P3: _clean_rewrite strips question-loop + softens absolutes -----------


def test_clean_rewrite_strips_validation_questions_section():
    raw = (
        "Fix the bug.\n\nContext: defect reported.\n\n"
        "Preguntas de validación:\n1. Which file?\n2. What error?"
    )
    cleaned = ip._clean_rewrite(raw, "fix the bug")
    assert cleaned is not None
    assert "Preguntas de validación" not in cleaned
    assert "Which file?" not in cleaned
    assert "Fix the bug" in cleaned


def test_clean_rewrite_strips_english_validation_questions():
    raw = "Add tests.\n\nContext: needs coverage.\n\nValidation questions:\n1. framework?"
    cleaned = ip._clean_rewrite(raw, "add tests")
    assert cleaned is not None
    assert "Validation questions" not in cleaned
    assert "framework?" not in cleaned


def test_clean_rewrite_softens_absolute_in_output():
    raw = "Add tests.\n\nAcceptance criteria: 100% coverage of all logic."
    cleaned = ip._clean_rewrite(raw, "add tests")
    assert "100% coverage" not in cleaned


# ---- Fast-path: concrete target --------------------------------------------


def test_has_concrete_target_true():
    assert ip.has_concrete_target("fix the bug in src/auth/login.py")
    assert ip.has_concrete_target("update the config.yaml timeouts")
    assert ip.has_concrete_target("edit app/components/header.tsx")
    assert ip.has_concrete_target("review src/app.py")


def test_has_concrete_target_false_for_vague():
    assert not ip.has_concrete_target("fix it")
    assert not ip.has_concrete_target("fix the bug")
    assert not ip.has_concrete_target("add tests")
    assert not ip.has_concrete_target("mejora el rendimiento")


# ---- P4: project hint ------------------------------------------------------


def test_project_hint_empty_when_no_cwd():
    assert ip._project_hint(None) == ""
    assert ip._project_hint("") == ""


def test_project_hint_reads_currenttask():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "# Current Task\n\n- Refactor the billing service to use events\n",
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "currentTask=" in hint
        assert "Refactor the billing service" in hint


def test_project_hint_skips_historical_completed_task_lines():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "\n".join(
                [
                    "# Current Task",
                    "- Status (2026-06-15, history): old Spring Boot migration",
                    "- RTK token-optimization subsystem (2026-06-15, COMPLETE): shipped",
                    "- Active: fix memory-bank project isolation for Claude hooks",
                ]
            ),
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "Spring Boot" not in hint
        assert "COMPLETE" not in hint
        assert "memory-bank project isolation" in hint


def test_project_hint_skips_last_deploy_when_no_active_task():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "\n".join(
                [
                    "# Current Task",
                    "## Estado: Sin tarea Codex activa (2026-07-01)",
                    "Ultimo trabajo Codex cerrado: mejoras moviles de ordenes y cotizaciones.",
                    "- T0-T5 + cleanup cosmetico: todos completos.",
                    "Ultimo deploy Codex: quote-conversion password guard.",
                ]
            ),
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "quote-conversion" not in hint
        assert "password guard" not in hint
        assert "currentTask=" not in hint


def test_project_hint_skips_checked_items_in_completed_currenttask():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "\n".join(
                [
                    "# currentTask",
                    "## Spring Boot 4 Migration Assistance (Completed)",
                    "Coordinating with Claude to resolve old test failures.",
                    "- [x] Fix UserGatewayImpl session handling.",
                    "- [ ] DEBT - extract shared SessionFilterHelper.",
                ]
            ),
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "UserGatewayImpl" not in hint
        assert "Coordinating with Claude" not in hint
        assert "SessionFilterHelper" in hint


def test_prompt_project_hint_omits_currenttask_for_concrete_continuation():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: quote-conversion password guard\n",
            encoding="utf-8",
        )
        hint = ip._project_hint_for_prompt(
            "continua con las mejoras moviles de cotizaciones; faltan boton y texto",
            d,
        )
        assert hint == f"cwd={Path(d).name}"
        assert "quote-conversion" not in hint


def test_prompt_project_hint_omits_currenttask_for_short_object_continuation():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: quote-conversion password guard\n",
            encoding="utf-8",
        )
        hint = ip._project_hint_for_prompt("continua con cotizaciones", d)
        assert hint == f"cwd={Path(d).name}"
        assert "quote-conversion" not in hint


def test_prompt_project_hint_keeps_currenttask_for_bare_continue():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: fix memory-bank project isolation\n",
            encoding="utf-8",
        )
        hint = ip._project_hint_for_prompt("continua", d)
        assert "currentTask=Active: fix memory-bank project isolation" in hint


def test_prompt_project_hint_keeps_currenttask_for_polite_bare_continue():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: fix memory-bank project isolation\n",
            encoding="utf-8",
        )
        hint = ip._project_hint_for_prompt("continua por favor", d)
        assert "currentTask=Active: fix memory-bank project isolation" in hint


def test_continuation_context_is_deterministic_from_currenttask():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: extract shared SessionFilterHelper so the no-op-close proxy "
            "lives in one place instead of duplicated in GenericBasicGatewayImpl "
            "and DeliveryOrderQueryDelegate\n",
            encoding="utf-8",
        )
        context = ip._continuation_context("continua", d)
        assert context is not None
        assert "extract shared SessionFilterHelper" in context
        assert "DeliveryOrderQueryDelegate" in context
        assert "verifica archivos" in context


def test_continuation_context_empty_without_currenttask():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "## Estado: Sin tarea Codex activa\nUltimo deploy: quote-conversion\n",
            encoding="utf-8",
        )
        assert ip._continuation_context("continua", d) is None


def test_project_hint_prefers_recent_active_task_over_generic_scope():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "\n".join(
                [
                    "# Current Task",
                    "- Maintain home-level cross-CLI config.",
                    "- **Status (2026-06-24):** completed memory subsystem hardening.",
                    "- **Active (2026-07-01):** improve second-opinion routing and memory freshness.",
                ]
            ),
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "second-opinion routing" in hint
        assert "Maintain home-level" not in hint
        assert ":**" not in hint


def test_project_hint_filters_stale_active_task_lines():
    # runner llama sin fixtures pytest — set/restore env manual
    prev = os.environ.get("MEMORY_INJECTION_ACTIVE_WINDOW_HOURS")
    os.environ["MEMORY_INJECTION_ACTIVE_WINDOW_HOURS"] = "12"
    try:
        with tempfile.TemporaryDirectory() as d:
            mb = Path(d) / ".memory-bank"
            mb.mkdir()
            (mb / "currentTask.md").write_text(
                "\n".join(
                    [
                        "# Current Task",
                        "- 2020-01-01T00:00:00Z | status:active | stale prompt-improver task",
                        "- 2026-01-01T00:00:00Z | status:live | stable prompt-improver task",
                    ]
                ),
                encoding="utf-8",
            )
            hint = ip._project_hint(d)
            assert "stale prompt-improver task" not in hint
            assert "stable prompt-improver task" in hint
    finally:
        if prev is None:
            os.environ.pop("MEMORY_INJECTION_ACTIVE_WINDOW_HOURS", None)
        else:
            os.environ["MEMORY_INJECTION_ACTIVE_WINDOW_HOURS"] = prev


def test_project_hint_without_memory_bank_returns_cwd_only():
    with tempfile.TemporaryDirectory() as d:
        hint = ip._project_hint(d)
        assert hint.startswith("cwd=")
        assert "currentTask=" not in hint


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


# ---- decide_mode -----------------------------------------------------------


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


# ---- data-driven eval fixtures ---------------------------------------------


def test_eval_fixture_properties():
    """Consume evals/prompt-improve.json and assert each declared property."""
    if not EVALS.exists():
        return  # no fixtures → nothing to assert
    data = json.loads(EVALS.read_text(encoding="utf-8"))
    for case in data.get("cases", []):
        cid = case.get("id", "?")
        prompt = case["prompt"]
        if "expect_trivial" in case:
            assert ip.detect_trivial(prompt) is case["expect_trivial"], f"[{cid}] trivial mismatch"
        if case.get("expect_concrete_target") is not None:
            assert ip.has_concrete_target(prompt) is case["expect_concrete_target"], (
                f"[{cid}] concrete mismatch"
            )
        if "expect_language" in case:
            assert ip.detect_language(prompt) == case["expect_language"], (
                f"[{cid}] language mismatch"
            )


# ---- real ollama smoke (skipped if no daemon) ------------------------------


def _ollama_available() -> bool:
    try:
        return bool(ip.available_ollama_models())
    except Exception:
        return False


def test_smoke_rewrite_no_es_leak_no_question_loop():
    """End-to-end: a real rewrite of an English prompt must not leak Spanish
    section headers, must not end with validation questions, and must not
    invent '100% coverage'. Skipped when ollama is unavailable."""
    import prompt_improve.shared.cache as cache_mod

    if not _ollama_available():
        import pytest

        pytest.skip("ollama not available")
    orig_ttl = cache_mod.CACHE_TTL_SECONDS
    cache_mod.CACHE_TTL_SECONDS = 0.0
    try:
        result = ip.call_ollama_rewrite("fix the bug")
    finally:
        cache_mod.CACHE_TTL_SECONDS = orig_ttl
    if result is None:
        import pytest

        pytest.skip("ollama returned no output")
    text = result[0]
    assert "Contexto:" not in text and "Objetivo:" not in text
    assert "Preguntas de validación" not in text.lower()
    assert "validation questions" not in text.lower()
    assert "100% coverage" not in text.lower()


# ---- intelligent router: hard prompts -> cloud (Ling), simple -> local --------


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

    def cloud(_p, _mode, _cwd=None, cloud_model=None):
        captured["cloud_model"] = cloud_model
        calls["cloud"] += 1
        return ("CLOUD", "cloud:deepseek-v4-flash")

    def local_rw(_p, _cwd=None):
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

    def local_rw(_p, _cwd=None):
        calls["local"] += 1
        return ("LOCAL", "ollama:batiai/gemma4-12b:q4")

    def cloud(_p, _mode, _cwd=None, cloud_model=None):
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

    def local_rw(_p, _cwd=None):
        return None

    def cloud(_p, _mode, _cwd=None, cloud_model=None):
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


# ---- cloud fallback (cheap_llm cascade: ling-2.6-flash/1t, gemini) ----------


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

    stub.cheap_complete = fake_complete
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
        try:
            import pytest

            pytest.skip("cheap_llm not importable")
        except ImportError:
            return
    if not os.environ.get("OPENROUTER_API_KEY"):
        try:
            import pytest

            pytest.skip("no OPENROUTER_API_KEY")
        except ImportError:
            return
    result = imod.call_cloud_cascade("fix the bug", "rewrite")
    if result is None:
        try:
            import pytest

            pytest.skip("cloud cascade unavailable")
        except ImportError:
            return
    text, src = result
    assert src.startswith("cloud:")
    assert "Contexto:" not in text
    assert "Preguntas de validación" not in text


# ---- role-based model routing tests ----------------------------------------


def test_role_model_map_exists():
    """_ROLE_MODEL_MAP is defined with expected roles."""
    assert hasattr(ip, "_ROLE_MODEL_MAP")
    assert "prompt_rewrite" in ip._ROLE_MODEL_MAP
    assert "prompt_clarify" in ip._ROLE_MODEL_MAP


def test_role_model_map_prefers_gemma4():
    """gemma4-12b is the first candidate for both prompt roles."""
    for role in ("prompt_rewrite", "prompt_clarify"):
        candidates = ip._ROLE_MODEL_MAP[role]
        assert len(candidates) >= 2, f"{role} should have at least 2 candidates"
        assert "gemma" in candidates[0].lower(), (
            f"{role} should prefer gemma4 first, got {candidates[0]}"
        )


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
    the universal qwen3.5:4b anchor (which sits last in the chain)."""
    import prompt_improve.shared.ollama as omod

    orig = omod.available_ollama_models
    omod.available_ollama_models = lambda: [
        "qwen3.5:4b",
        "Librellama/gemma4:e2b-Uncensored",
    ]
    orig_start = omod.start_ollama_best_effort
    omod.start_ollama_best_effort = lambda: True
    try:
        primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")
        assert primary is not None
        # Librellama/gemma4:e2b-Uncensored is ahead of qwen3.5:4b in the role chain → must win
        assert "gemma" in primary.lower()
        assert len(fallbacks) >= 1
    finally:
        omod.available_ollama_models = orig
        omod.start_ollama_best_effort = orig_start


def test_choose_model_for_role_falls_back_when_primary_unavailable():
    """When gemma4 is unavailable, qwen3.5:4b is chosen."""
    import prompt_improve.shared.ollama as omod

    orig = omod.available_ollama_models
    omod.available_ollama_models = lambda: ["qwen3.5:4b", "some-other-model"]
    orig_start = omod.start_ollama_best_effort
    omod.start_ollama_best_effort = lambda: True
    try:
        primary, fallbacks = omod.choose_ollama_model_for_role("prompt_rewrite")
        assert primary == "qwen3.5:4b"
    finally:
        omod.available_ollama_models = orig
        omod.start_ollama_best_effort = orig_start


def test_choose_model_for_role_env_override():
    """OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE env var overrides the default."""
    import prompt_improve.shared.config as cfg
    import prompt_improve.shared.ollama as omod

    orig_env = os.environ.get("OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE")
    orig_models = omod.available_ollama_models
    omod.available_ollama_models = lambda: ["custom-model:latest", "qwen3.5:4b"]
    orig_start = omod.start_ollama_best_effort
    omod.start_ollama_best_effort = lambda: True
    try:
        orig_map = cfg._ROLE_MODEL_MAP.copy()
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


# ---- clean module: direct unit tests ----------------------------------------


def test_trim_bullet_short_line_unchanged():
    assert ip._trim_bullet("short line") == "short line"


def test_trim_bullet_trims_at_sentence_boundary():
    long = "A" * 80 + ". " + "B" * 80 + ". " + "C" * 80
    result = ip._trim_bullet(long, limit=180)
    assert len(result) <= 180
    assert result.endswith(".")


def test_trim_bullet_trims_at_comma_if_no_sentence():
    long = "A" * 80 + ", " + "B" * 80 + ", " + "C" * 80
    result = ip._trim_bullet(long, limit=180)
    assert len(result) <= 180
    assert result.endswith("...")


def test_trim_bullet_hard_cutoff_for_very_long_word():
    long = "A" * 200
    result = ip._trim_bullet(long, limit=180)
    assert len(result) <= 180
    assert result.endswith("...")


def test_remove_long_examples_removes_parenthetical():
    line = "Check auth (for example, OAuth2, SAML, and JWT tokens) carefully"
    shortened = ip._remove_long_examples(line)
    assert "for example" not in shortened
    assert "Check auth" in shortened


def test_remove_long_examples_keeps_short_parenthetical():
    line = "Use OAuth2 (preferred) for auth"
    shortened = ip._remove_long_examples(line)
    assert shortened == line  # no change — parenthetical is short


def test_sanitize_bullet_replaces_noisy_tools():
    line = "- Use OWASP ZAP and Burp Suite to scan for vulnerabilities"
    result = ip._sanitize_bullet(line)
    assert "OWASP ZAP" not in result
    assert "Burp Suite" not in result
    assert "security" in result.lower() or "seguridad" in result.lower()


def test_sanitize_bullet_keeps_clean_line():
    line = "- Verify the auth flow with grep and LSP"
    assert ip._sanitize_bullet(line) == line


def test_clean_response_returns_none_for_empty():
    assert ip._clean_response("", "original") is None
    assert ip._clean_response("   ", "original") is None


def test_clean_response_returns_none_when_same_as_original():
    assert ip._clean_response("fix the bug", "fix the bug") is None


def test_clean_response_strips_think_tags():
    raw = "<think>thinking about this</think>\n- Check the auth module"
    result = ip._clean_response(raw, "original")
    assert result is not None
    assert "<think>" not in result
    assert "Check the auth" in result


def test_clean_response_limits_to_three_bullets():
    raw = "- Bullet 1\n- Bullet 2\n- Bullet 3\n- Bullet 4\n- Bullet 5"
    result = ip._clean_response(raw, "original")
    assert result is not None
    assert result.count("\n") == 2  # 3 bullets = 2 newlines


def test_clean_rewrite_returns_none_for_short_text():
    assert ip._clean_rewrite("hi", "original prompt") is None


def test_clean_rewrite_returns_none_when_same_as_original():
    assert ip._clean_rewrite("fix the bug", "fix the bug") is None


def test_clean_rewrite_strips_preamble():
    raw = "Here is the rewritten prompt:\n\nFix the authentication bug in the login flow."
    result = ip._clean_rewrite(raw, "fix auth")
    assert result is not None
    assert "here is" not in result.lower()
    assert "Fix the authentication" in result


# ---- fallback chain: OllamaRequestError vs OllamaUnavailable ---------------
# Regression for the model-load-failure bug: a primary that fails to LOAD
# (HTTP 500 — common under VRAM contention with many models installed) must
# NOT abort the whole fallback chain. Only a daemon-down (URLError/timeout)
# aborts. These tests are fixture-free so they run under both pytest and _run_all().

_FAKE_REWRITE = (
    "Goal: fix the dashboard load performance.\n\n"
    "Steps:\n"
    "- Profile the initial render with browser devtools to find the slow components.\n"
    "- Add lazy loading for the chart components below the fold.\n"
    "- Memoize the expensive selectors.\n\n"
    "Verify: the dashboard paints in under one second on a cold load."
)


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


def test_fallback_chain_continues_past_model_load_failure():
    """Primary raises OllamaRequestError (HTTP 500 / VRAM load failure) → the
    chain MUST advance to the fallback and succeed, not abort."""
    mod, calls, saved, ReqErr, _Unavail, fake_chat = _patch_runner()
    fake_chat._next = _seq_responder([ReqErr("HTTP 500: unable to load model"), _FAKE_REWRITE])
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
    fake_chat._next = _seq_responder([Unavail("connection refused")])
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
    fake_chat._next = _seq_responder(["", "   ", _FAKE_REWRITE])
    mod.choose_ollama_model_for_role = lambda role: (
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


# ---- unittest fallback (run without pytest) --------------------------------


def _run_all() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())


# ---- command.main end-to-end (UserPromptSubmit hook) --------------------


def _run_main_via_stdin(prompt: str, cwd: str | None = None, env: dict | None = None):
    """Drive command.main() as if invoked by Claude Code's hook runtime."""
    from prompt_improve import command

    payload = {"prompt": prompt}
    if cwd is not None:
        payload["cwd"] = cwd
    stdin_bytes = json.dumps(payload).encode("utf-8")
    saved_stdin = sys.stdin
    saved_stdout = sys.stdout
    saved_env = {
        k: os.environ.get(k)
        for k in (
            "NO_DELEGATE",
            "NO_IMPROVE",
            "CODEX_WORKER",
            "SWARM_WORKER",
        )
    }
    try:
        sys.stdin = io.BytesIO(stdin_bytes)
        sys.stdout = io.StringIO()
        if env:
            for k, v in env.items():
                os.environ[k] = v
                os.environ.pop(k, None) if v is None else None
        command.main()
        return sys.stdout.getvalue()
    finally:
        sys.stdin = saved_stdin
        sys.stdout = saved_stdout
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_command_main_passthrough_on_no_improve_marker():
    """[NO_IMPROVE] bypasses everything — emits a bare continue=true."""
    out = _run_main_via_stdin("implement the feature", env={"NO_IMPROVE": "1"})
    assert json.loads(out) == {"continue": True}


def test_command_main_passthrough_on_trivial_prompt():
    """Short acknowledgments must not invoke the LLM."""
    out = _run_main_via_stdin("ok thanks")
    assert json.loads(out) == {"continue": True}


def test_command_main_falls_through_when_no_model_available():
    """When LLM fails AND rule fallback yields nothing, emit bare continue."""
    # "asdfgh" with no TASK_VERBS and no Spanish markers — rule-based yields
    # nothing and we mock call_ollama_rewrite to return None (cold/dead daemon).
    import prompt_improve.command as cmd

    orig = cmd.route_and_improve
    cmd.route_and_improve = lambda _p, _mode, _cwd=None: None
    try:
        out = _run_main_via_stdin("asdfgh qwerty", cwd="/nonexistent")
    finally:
        cmd.route_and_improve = orig
    # Either bare continue (no improvement available) or hint — but never raises.
    parsed = json.loads(out)
    assert parsed.get("continue") is True


def test_command_main_emits_additional_context_on_rewrite():
    """Happy path: rewrite mode routes through an LLM, wraps the output as
    hookSpecificOutput.additionalContext (NOT a user-facing question)."""
    import prompt_improve.command as cmd

    def fake_route(_prompt, _mode, _cwd=None):
        return ("Tarea: Hacer X.\n\nContexto: y.", "ollama:fake", "rewrite")

    orig = cmd.route_and_improve
    cmd.route_and_improve = fake_route
    # "implementa la funcion foo" passes detect_trivial (matches TASK_VERBS)
    # and avoids has_concrete_target (no file/path substring).
    try:
        out = _run_main_via_stdin("implementa la funcion foo", cwd="/nonexistent")
    finally:
        cmd.route_and_improve = orig
    parsed = json.loads(out)
    ctx = parsed["hookSpecificOutput"]["additionalContext"]
    assert "[Prompt expandido" in ctx
    assert "fake" in ctx
    assert "Tarea" in ctx
