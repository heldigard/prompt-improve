"""Tests for prompt_improve.features.detect: detect_trivial, detect_language, has_concrete_target."""

from __future__ import annotations

from tests import compat as ip

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
