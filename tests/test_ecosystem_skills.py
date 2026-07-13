from __future__ import annotations

from pathlib import Path
from prompt_improve.shared.paths import project_hint_for_prompt, _ecosystem_skill_hint
from prompt_improve.features.rules import rule_based_suggestions


def test_ecosystem_skill_hint_detection_english() -> None:
    # Angular
    hint = _ecosystem_skill_hint("make an angular component", "English")
    assert "ecosystem guideline: For Angular, use Angular v22" in hint

    # React
    hint = _ecosystem_skill_hint("create a react component", "English")
    assert "ecosystem guideline: For React, use React 19" in hint

    # CSS
    hint = _ecosystem_skill_hint("write some css styles", "English")
    assert "ecosystem guideline: For CSS, use modern vanilla CSS" in hint

    # Python
    hint = _ecosystem_skill_hint("write fastapi endpoint in python", "English")
    assert "ecosystem guideline: For Python, use strict type hints" in hint


def test_ecosystem_skill_hint_detection_spanish() -> None:
    # Angular
    hint = _ecosystem_skill_hint("crear un componente de angular", "Spanish")
    assert "pauta del ecosistema: Para Angular, usa Angular v22" in hint

    # React
    hint = _ecosystem_skill_hint("hacer un componente en react", "Spanish")
    assert "pauta del ecosistema: Para React, usa React 19" in hint

    # CSS
    hint = _ecosystem_skill_hint("escribir estilos de css", "Spanish")
    assert "pauta del ecosistema: Para CSS, usa CSS moderno puro" in hint


def test_ecosystem_skill_hint_implicit_language() -> None:
    # Implicit Spanish
    hint = _ecosystem_skill_hint("crea un componente en angular")
    assert "pauta del ecosistema" in hint

    # Implicit English
    hint = _ecosystem_skill_hint("create angular component")
    assert "ecosystem guideline" in hint


def test_project_hint_appends_ecosystem_skill(tmp_path: Path) -> None:
    hint = project_hint_for_prompt("write a react view", str(tmp_path), "English")
    assert "cwd=" in hint
    assert "ecosystem guideline: For React" in hint


def test_rule_based_suggestions_for_ecosystem_skills() -> None:
    # Angular missing key features
    suggestions = rule_based_suggestions("create an angular component")
    assert suggestions is not None
    assert "standalone components, signals, zoneless" in suggestions

    # React missing key features
    suggestions = rule_based_suggestions("cómo crear un componente de react")
    assert suggestions is not None
    assert "Server Components, Actions y useActionState" in suggestions

    # CSS missing key features
    suggestions = rule_based_suggestions("write css style sheet")
    assert suggestions is not None
    assert "modern vanilla CSS" in suggestions

    # Python missing key features
    suggestions = rule_based_suggestions("cómo escribir endpoints en python")
    assert suggestions is not None
    assert "tipado estricto (evitar Any), Pydantic v2" in suggestions
