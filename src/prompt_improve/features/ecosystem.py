"""Ecosystem skill hints: deterministic prompt → preferred-stack guideline.

Extracted from ``shared/paths.py`` so that module keeps a single responsibility
(memory-bank discovery). Lives in ``features/`` because it depends on
``features.detect`` — a dependency ``shared/`` must not take.
"""

from __future__ import annotations

import re

from prompt_improve.features.detect import detect_language

# Ordered (pattern, hint_es, hint_en). First match wins: specific stacks
# (Foundry, Azure Functions) must precede the generic language branches.
_ECOSYSTEM_RULES: tuple[tuple[str, str, str], ...] = (
    # Microsoft Foundry: use the canonical installed skill name; marketplace
    # source-tree names are not guaranteed invocable in the receiving CLI.
    (
        r"\b(?:microsoft|azure|ai)[- ]?foundry\b|\bfoundry[- ]?(?:agent|project|eval)\b|"
        r"\b(?:azure|foundry)\b.{0,120}\breasoning summar(?:y|ies)\b|"
        r"\breasoning summar(?:y|ies)\b.{0,120}\b(?:azure|foundry)\b",
        "pauta del ecosistema: Para Microsoft Foundry, carga la skill azure-foundry-agents; usa Responses API, reasoning summaries (nunca chain-of-thought crudo), trazas con acceso restringido y validación antes de desplegar.",
        "ecosystem guideline: For Microsoft Foundry, load the azure-foundry-agents skill; use the Responses API, reasoning summaries (never raw chain-of-thought), access-controlled traces, and validation before deploy.",
    ),
    # Azure Functions before the generic Python branch.
    (
        r"\bazure[- ]?functions?\b|\bfunction[- ]?app\b|\bfunction_app\.py\b|\b(?:http|timer|blob)trigger\b",
        "pauta del ecosistema: Para Azure Functions, carga azure-functions y azure-functions-python cuando aplique; prefiere Flex Consumption para Linux nuevo, identidad administrada y despliegue por pipeline.",
        "ecosystem guideline: For Azure Functions, load azure-functions and azure-functions-python when applicable; prefer Flex Consumption for new Linux apps, managed identity, and pipeline deployment.",
    ),
    (
        r"\bangular\b|\bng-|\b@angular\b|\bngx-",
        "pauta del ecosistema: Para Angular, usa Angular v22, componentes standalone, signals+zoneless, @if/@for, inject() y Signal Forms.",
        "ecosystem guideline: For Angular, use Angular v22, standalone, signals+zoneless, @if/@for, inject(), and Signal Forms.",
    ),
    (
        r"\breact\b|\bjsx\b|\btsx\b|\bnextjs\b|\bnext\.js\b",
        "pauta del ecosistema: Para React, usa React 19, Server Components, Actions y useActionState/useOptimistic.",
        "ecosystem guideline: For React, use React 19, Server Components, Actions, and useActionState/useOptimistic.",
    ),
    (
        r"\bsvelte\b|\bsveltekit\b",
        "pauta del ecosistema: Para Svelte, usa Svelte 5 runes ($state, $derived, $effect, $props) y sintaxis onclick.",
        "ecosystem guideline: For Svelte, use Svelte 5 runes ($state, $derived, $effect, $props) and onclick event syntax.",
    ),
    (
        r"\bvue\b|\bvuejs\b|\bpinia\b|\bnuxt\b",
        "pauta del ecosistema: Para Vue, usa Vue 3.5 Composition API, <script setup> y Pinia.",
        "ecosystem guideline: For Vue, use Vue 3.5 Composition API, <script setup>, and Pinia.",
    ),
    (
        r"\btailwind\b|\btailwindcss\b",
        "pauta del ecosistema: Para Tailwind, usa Tailwind CSS v4, motor Oxide y configuración @theme.",
        "ecosystem guideline: For Tailwind, use Tailwind CSS v4, Oxide engine, and @theme configuration.",
    ),
    # CSS (after Tailwind).
    (
        r"\bcss\b|\bstyling\b|\bstyle\b|\bestilos\b|\bestilo\b|\bdiseño\b",
        "pauta del ecosistema: Para CSS, usa CSS moderno puro (container queries, :has, @layer, oklch, grid/flex) y evita Tailwind a menos que se pida expresamente.",
        "ecosystem guideline: For CSS, use modern vanilla CSS (container queries, :has, @layer, oklch, grid/flex) and avoid Tailwind unless explicitly requested.",
    ),
    (
        r"\bpython\b|\bpy\b|\bfastapi\b|\bsqlalchemy\b|\bpydantic\b",
        "pauta del ecosistema: Para Python, usa tipado estricto (evitar Any), Pydantic v2 y async/await. Captura solo excepciones específicas.",
        "ecosystem guideline: For Python, use strict type hints (no Any), Pydantic v2, and async/await. Catch only specific exceptions.",
    ),
    (
        r"\btypescript\b|\bts\b|\bjavascript\b|\bjs\b|\bnode\b|\bnodejs\b",
        "pauta del ecosistema: Para JS/TS, usa ES2023+, ESM, type-safe guards e imports limpios.",
        "ecosystem guideline: For JS/TS, use ES2023+, ESM, type-safe guards, and clean imports.",
    ),
    (
        r"\bgit commit\b|\bcommit message\b|\bgit log\b|\bmensaje de commit\b|\bconvencional\b",
        "pauta del ecosistema: Para git commits, escribe un mensaje de commit convencional (Conventional Commit) que coincida con el skill git-commit.",
        "ecosystem guideline: For git commits, write a Conventional Commit message matching the git-commit skill.",
    ),
    (
        r"\bmemory bank\b|\bmemoria\b|\b\.memory-bank\b|\bcurrenttask\b|\bactivecontext\b|\bprogress\.md\b",
        "pauta del ecosistema: Para memoria, actualiza y mantén los archivos de .memory-bank (MEMORY.md, CONTEXT.md, progress.md) usando la estructura del skill agent-memory.",
        "ecosystem guideline: For memory, update/maintain memory files (MEMORY.md, CONTEXT.md, progress.md) using agent-memory skill structure.",
    ),
    (
        r"\bjpa\b|\bhibernate\b|\bspring boot\b|\bspring-boot\b",
        "pauta del ecosistema: Para Spring Boot/JPA, evita consultas N+1, usa lazy loading y respeta límites transaccionales.",
        "ecosystem guideline: For Spring Boot/JPA, avoid N+1 queries, use lazy loading, and follow transactional boundaries.",
    ),
    (
        r"\bnestjs\b|\b@nestjs\b",
        "pauta del ecosistema: Para NestJS, usa arquitectura modular (módulos, controladores, servicios), DTOs e inyección de dependencias.",
        "ecosystem guideline: For NestJS, use modular architecture, controllers, services, DTOs, and dependency injection.",
    ),
    (
        r"\bplaywright\b|\bwebdriver\b|\bselenium\b|\bbrowser automation\b|\bautomatizaci[oó]n de navegador\b|\bscraping\b|\bscrape\b",
        "pauta del ecosistema: Para automatización de navegador, usa el CLI agent-browser con referencias a elementos (no coordenadas). Para pruebas, usa Playwright .spec.ts.",
        "ecosystem guideline: For browser automation, use agent-browser CLI with element REFs (not coordinates). For browser tests, use Playwright .spec.ts.",
    ),
    (
        r"\bkubernetes\b|\bk8s\b|\bhelm\b|\bkubectl\b",
        "pauta del ecosistema: Para Kubernetes, usa Gateway API, Helm, GitOps (ArgoCD/Flux) y sidecars nativos.",
        "ecosystem guideline: For Kubernetes, prefer Gateway API, Helm, GitOps (ArgoCD/Flux), and native sidecars.",
    ),
    # Java last: Spring Boot / JPA match earlier.
    (
        r"\bjava\b|\bmaven\b|\bgradle\b|\bpom\.xml\b",
        "pauta del ecosistema: Para Java, usa manejo de excepciones personalizado, SLF4J/MDC para logging estructurado y virtual threads para concurrencia.",
        "ecosystem guideline: For Java, use custom exception handling, SLF4J/MDC for structured logging, and virtual threads for concurrency.",
    ),
)

_ECOSYSTEM_RULES_COMPILED: tuple[tuple[re.Pattern[str], str, str], ...] = tuple(
    (re.compile(pattern), hint_es, hint_en) for pattern, hint_es, hint_en in _ECOSYSTEM_RULES
)


def ecosystem_skill_hint(prompt: str, language: str | None = None) -> str:
    """Return a short guideline hint if the prompt relates to a registered ecosystem skill.

    Deterministic keyword matching that guides the LLM to structure prompt expansion
    using our local ecosystem's preferred patterns and version requirements.
    """
    p = prompt.lower()
    if language is None:
        language = detect_language(prompt)
    is_sp = language == "Spanish"
    for pattern, hint_es, hint_en in _ECOSYSTEM_RULES_COMPILED:
        if pattern.search(p):
            return hint_es if is_sp else hint_en
    return ""
