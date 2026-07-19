from __future__ import annotations

from pathlib import Path

from prompt_improve.features.ecosystem import ecosystem_skill_hint
from prompt_improve.features.hints import project_hint_for_prompt
from prompt_improve.features.rules import rule_based_suggestions


def test_ecosystem_skill_hint_detection_english() -> None:
    hint = ecosystem_skill_hint(
        "design Microsoft Foundry reasoning summaries and traces", "English"
    )
    assert "azure-foundry-agents" in hint
    assert "raw chain-of-thought" in hint

    assert "azure-foundry-agents" not in ecosystem_skill_hint(
        "compare OpenAI reasoning summaries with local model output", "English"
    )

    hint = ecosystem_skill_hint("build an Azure Functions Python function_app.py", "English")
    assert "azure-functions-python" in hint
    assert "Flex Consumption" in hint

    # Angular
    hint = ecosystem_skill_hint("make an angular component", "English")
    assert "ecosystem guideline: For Angular, use Angular v22" in hint

    # React
    hint = ecosystem_skill_hint("create a react component", "English")
    assert "ecosystem guideline: For React, use React 19" in hint

    # CSS
    hint = ecosystem_skill_hint("write some css styles", "English")
    assert "ecosystem guideline: For CSS, use modern vanilla CSS" in hint

    # Python
    hint = ecosystem_skill_hint("write fastapi endpoint in python", "English")
    assert "ecosystem guideline: For Python, use strict type hints" in hint

    # NestJS
    hint = ecosystem_skill_hint("setup a nestjs controller", "English")
    assert "ecosystem guideline: For NestJS, use modular architecture" in hint

    # Browser
    hint = ecosystem_skill_hint("write browser automation script in playwright", "English")
    assert "ecosystem guideline: For browser automation, use agent-browser CLI" in hint

    # Kubernetes
    hint = ecosystem_skill_hint("deploy to kubernetes using helm", "English")
    assert "ecosystem guideline: For Kubernetes, prefer Gateway API" in hint

    # Java
    hint = ecosystem_skill_hint("build maven project in java", "English")
    assert "ecosystem guideline: For Java, use custom exception handling" in hint


def test_ecosystem_skill_hint_detection_spanish() -> None:
    hint = ecosystem_skill_hint("crear agente en Microsoft Foundry", "Spanish")
    assert "azure-foundry-agents" in hint

    hint = ecosystem_skill_hint("crear Azure Functions con Python", "Spanish")
    assert "azure-functions-python" in hint

    # Angular
    hint = ecosystem_skill_hint("crear un componente de angular", "Spanish")
    assert "pauta del ecosistema: Para Angular, usa Angular v22" in hint

    # React
    hint = ecosystem_skill_hint("hacer un componente en react", "Spanish")
    assert "pauta del ecosistema: Para React, usa React 19" in hint

    # CSS
    hint = ecosystem_skill_hint("escribir estilos de css", "Spanish")
    assert "pauta del ecosistema: Para CSS, usa CSS moderno puro" in hint

    # NestJS
    hint = ecosystem_skill_hint("configurar controlador nestjs", "Spanish")
    assert "pauta del ecosistema: Para NestJS, usa arquitectura modular" in hint

    # Browser
    hint = ecosystem_skill_hint("hacer scraping con playwright", "Spanish")
    assert (
        "pauta del ecosistema: Para automatización de navegador, usa el CLI agent-browser" in hint
    )

    # Kubernetes
    hint = ecosystem_skill_hint("desplegar en kubernetes", "Spanish")
    assert "pauta del ecosistema: Para Kubernetes, usa Gateway API" in hint

    # Java
    hint = ecosystem_skill_hint("proyecto java con maven", "Spanish")
    assert "pauta del ecosistema: Para Java, usa manejo de excepciones personalizado" in hint


def test_ecosystem_skill_hint_implicit_language() -> None:
    # Implicit Spanish
    hint = ecosystem_skill_hint("crea un componente en angular")
    assert "pauta del ecosistema" in hint

    # Implicit English
    hint = ecosystem_skill_hint("create angular component")
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

    # NestJS missing key features
    suggestions = rule_based_suggestions("cómo configurar nestjs")
    assert suggestions is not None
    assert "arquitectura modular (módulos, controladores, servicios)" in suggestions

    # Browser missing key features
    suggestions = rule_based_suggestions("run a playwright browser flow")
    assert suggestions is not None
    assert "element REFs (not coordinates) with agent-browser CLI" in suggestions

    # Kubernetes missing key features
    suggestions = rule_based_suggestions("cómo configurar kubernetes")
    assert suggestions is not None
    assert "Gateway API, Helm y GitOps (ArgoCD/Flux)" in suggestions

    # Java missing key features
    suggestions = rule_based_suggestions("build a java library")
    assert suggestions is not None
    assert "custom exception handling, SLF4J/MDC for logging" in suggestions
