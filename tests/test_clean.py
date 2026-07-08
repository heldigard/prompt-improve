"""Tests for prompt_improve.features.clean: output cleaning, bullet trimming, softening absolutes, stripping validation questions, and rewrite output-shaping (language-correct section labels)."""

from __future__ import annotations

from tests import compat as ip


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


def test_rewrite_prompt_forbids_user_questions_and_absolutes():
    en = ip.build_rewrite_system_prompt("English")
    es = ip.build_rewrite_system_prompt("Spanish")
    assert "questions for the user" in en.lower()
    assert "100% coverage" in en
    assert "100% cobertura" in es


def test_soften_absolutes_english():
    assert "100% coverage" not in ip._soften_invented_absolutes("Ensure 100% coverage")
    assert "zero downtime" not in ip._soften_invented_absolutes("zero downtime guaranteed")
    assert "broad test coverage" in ip._soften_invented_absolutes("Require full test coverage")


def test_soften_absolutes_spanish():
    out = ip._soften_invented_absolutes("Garantizar 100% de cobertura y cobertura total")
    assert "100% de cobertura" not in out
    assert "cobertura total" not in out


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
