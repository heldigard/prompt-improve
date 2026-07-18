"""Tests for prompt classification and authority gates."""

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


def test_detect_language_ignores_spanish_substrings_inside_english_words():
    # Bug fix 2026-07-11: substring matching flagged English words containing
    # "que" (request/query/unique/sequence) as Spanish, so the rewrite came
    # back in the wrong language. Markers now require word boundaries.
    assert ip.detect_language("improve the request queue") == "English"
    assert ip.detect_language("fix the query builder") == "English"
    assert ip.detect_language("unique constraint fails on insert") == "English"
    assert ip.detect_language("run the test sequence again") == "English"
    # Standalone Spanish function words still match.
    assert ip.detect_language("como se usa esto") == "Spanish"


def test_has_concrete_target_true():
    assert ip.has_concrete_target("fix the bug in src/auth/login.py")
    assert ip.has_concrete_target("update the config.yaml timeouts")
    assert ip.has_concrete_target("edit app/components/header.tsx")
    assert ip.has_concrete_target("review src/app.py")
    assert ip.has_concrete_target("revisa ollama bech para establecer el modelo numero uno real")
    assert ip.has_concrete_target(
        "revisa prompt-improve, smart-trim y ollama-client y corrige sus contratos"
    )
    assert ip.has_concrete_target(
        "optimize a slow PostgreSQL query with explain analyze indexes"
    )
    assert ip.has_concrete_target(
        "mejora el ecosistema cross-cli para ahorrar tokens sin perder calidad"
    )


def test_has_concrete_target_false_for_vague():
    assert not ip.has_concrete_target("fix it")
    assert not ip.has_concrete_target("fix the bug")
    assert not ip.has_concrete_target("add tests")
    assert not ip.has_concrete_target("mejora el rendimiento")
    assert not ip.has_concrete_target("fix this API thing because it fails")
    assert not ip.has_concrete_target("improve this test please because it is bad")
    assert not ip.has_concrete_target("review the service and make it better somehow")


def test_depends_on_conversation_context():
    assert ip.depends_on_conversation_context("arregla lo que hablamos ayer")
    assert ip.depends_on_conversation_context("implement what we discussed")
    assert ip.depends_on_conversation_context("como dijimos, corrige eso")
    assert not ip.depends_on_conversation_context("corrige el parser en src/config.py")


def test_rule_based_suggestions_localized_to_prompt_language():
    from prompt_improve.features.rules import rule_based_suggestions

    en = rule_based_suggestions("please fix it now, something broken somewhere")
    assert en is not None
    assert en.startswith("Suggestions to clarify the prompt:")
    assert "Especifica" not in en

    es = rule_based_suggestions("arregla eso que está roto por favor")
    assert es is not None
    assert es.startswith("Sugerencias para clarificar el prompt:")
    assert "Specify" not in es


# --- native Claude XML passthrough -------------------------------------------
# Native Claude Code emits <task>/<objective>/<context>/<constraints>/<acceptance>
# blocks when it classifies the user prompt. A second rewrite from prompt-improve
# would dilute that structure, so has_concrete_target() must detect the closing
# tag and short-circuit to passthrough. Closing tag required — a half-typed
# `<task>` does NOT passthrough (the prompt could still be vague content).
_NATIVE_XML_PASSTHROUGH = [
    "<task>Fix the login bug</task>",
    "<objective>Reduce latency under 200ms</objective>",
    "<context>Working on smart-trim v3.4\n<context>deploy target is prod</context>\n<task>ship it</task>",
    "<constraints>no new deps</constraints>\n<acceptance>all tests pass</acceptance>",
    "<task>\n  ship smart-trim 3.4\n</task>\n\nignore above",
    "<TASK>case-insensitive match</TASK>",
]


def test_has_concrete_target_true_for_native_claude_xml():
    for p in _NATIVE_XML_PASSTHROUGH:
        assert ip.has_concrete_target(p) is True, f"should passthrough: {p!r}"


def test_has_concrete_target_false_for_unclosed_xml_tag():
    """A half-typed opening tag must NOT trigger passthrough — user might be
    describing content literally ('the <task> tag in our schema') or pasting
    XML mid-edit."""
    assert not ip.has_concrete_target("<task> open ended, no closing tag")
    assert not ip.has_concrete_target("explain the <task> tag in our XML schema")


def test_has_concrete_target_false_for_unrelated_xml():
    """Plain XML that is NOT one of the native Claude tags must not passthrough
    — only task/objective/context/constraints/acceptance are Claude's
    classifier output. A <div> or <script> block is unrelated content."""
    assert not ip.has_concrete_target("<div>some html</div>")
    assert not ip.has_concrete_target("<script>alert(1)</script>")


def test_has_concrete_target_short_native_xml_passthrough():
    """Native XML passthrough must NOT require a long prompt — the closing
    tag is the only signal we need."""
    assert ip.has_concrete_target("<task>x</task>")


def test_has_concrete_target_relative_dot_path() -> None:
    from prompt_improve.features.detect import has_concrete_target

    assert has_concrete_target("fix ./foo.py") is True


def test_has_concrete_target_home_relative_path() -> None:
    from prompt_improve.features.detect import has_concrete_target

    assert has_concrete_target("update ~/projects/x.py") is True


def test_has_concrete_target_absolute_path() -> None:
    from prompt_improve.features.detect import has_concrete_target

    assert has_concrete_target("review /home/eldi/x.py") is True


def test_has_concrete_target_quoted_relative_path() -> None:
    from prompt_improve.features.detect import has_concrete_target

    assert has_concrete_target('lint "src/foo.ts"') is True


def test_has_concrete_target_false_when_no_path_or_ext() -> None:
    from prompt_improve.features.detect import has_concrete_target

    assert has_concrete_target("fix it") is False
    assert has_concrete_target("update this thing") is False
    assert has_concrete_target("fix foo") is False


def test_detect_trivial_slash_with_args() -> None:
    """Slash-command with arguments is an actionable command — passthrough."""
    from prompt_improve.features.detect import detect_trivial

    assert detect_trivial("/commit the changes") is True
    assert detect_trivial("/review src/foo.py") is True
    assert detect_trivial("/plan add caching layer") is True


def test_detect_trivial_bare_slash() -> None:
    """Bare slash-commands still pass through (unchanged behavior)."""
    from prompt_improve.features.detect import detect_trivial

    assert detect_trivial("/commit") is True
