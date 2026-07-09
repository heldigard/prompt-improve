"""Rule-based suggestions and system prompts (LLM fallback)."""

from __future__ import annotations

import re

from prompt_improve.features.target import GENERIC_TARGET, TargetProfile, target_guidance

SYSTEM_PROMPT = (
    "You are a prompt-clarity assistant for an AUTONOMOUS coding agent — not a human.\n"
    "The agent can inspect local evidence and execute the work itself.\n"
    "Return 1-3 concise bullets that help the agent act MORE effectively. Each bullet "
    "must tell the agent what to DO or VERIFY (an action it can take), NOT what to ask "
    "the user for. Only request user input for genuinely undiscoverable facts "
    "(credentials, business preference, or bug-reproduction steps absent from context).\n"
    "Maintain the user's language. Do not rewrite the full prompt. Do not invent "
    "tools, frameworks, files, standards, or requirements the user did not imply. "
    "Preserve every project name, path, model identifier, and stated relationship "
    "as evidence. Do not reinterpret a project name as a language or tool. "
    "Do not mention that you are an AI.\n"
    "Agent-oriented heuristics:\n"
    "- Bug-fix without evidence: the agent should grep for the reported symptom and "
    "ask for the error text only if it is absent from the prompt AND undiscoverable.\n"
    "- Refactor/analysis: the agent should inspect definitions and call sites before "
    "editing, then run focused verification after.\n"
    "- Research/documentation: verify claims against the named source of truth; do "
    "not turn it into an implementation task or generic quality scan.\n"
    "- Create without criteria: the agent should confirm success via a runnable test.\n"
    "- Long (>400 chars) without labeled sections: suggest flat sections "
    "(Task / Context / Source / Constraints / Output).\n"
    "- Source material present (code/log/file): the Task is read best when placed "
    "AFTER the source.\n"
    "- Multi-step without numbering: suggest numbering the steps.\n"
    "Format exactly as bullets:\n"
    "- ...\n"
)


def build_rewrite_system_prompt(
    language: str,
    target: TargetProfile = GENERIC_TARGET,
) -> str:
    """Language-aware rewrite system prompt."""
    if language == "Spanish":
        task_kw, ctx, obj, constr, accept = (
            "Tarea",
            "Contexto",
            "Objetivo",
            "Restricciones",
            "Criterios de aceptación",
        )
        agent_note = (
            "Si la intención es genuinamente ambigua, añade una línea 'Nota para el "
            "agente:' indicando qué evidencia local debe verificar antes de actuar."
        )
        absolutes = "objetivos numéricos absolutos (ej. '100% cobertura', 'cero downtime')"
    else:
        task_kw, ctx, obj, constr, accept = (
            "Task",
            "Context",
            "Objective",
            "Constraints",
            "Acceptance criteria",
        )
        agent_note = (
            "If intent is genuinely ambiguous, add an 'Agent note:' line stating "
            "which local evidence must be verified before acting."
        )
        absolutes = "absolute numeric targets (e.g. '100% coverage', 'zero downtime')"
    return (
        "You are a prompt-engineering assistant for an AUTONOMOUS coding agent. "
        "The user wrote a SHORT, vague prompt. Rewrite it into a clear, actionable, "
        "structured prompt that captures their evident intent without inventing "
        "requirements they did not imply.\n"
        "Hard rules:\n"
        "- Preserve the user's language (Spanish stays Spanish, English stays English).\n"
        "- Output ONLY the rewritten prompt. No preamble, no explanations, no "
        "meta-commentary, no 'Here is...'.\n"
        "- Do NOT invent technologies, frameworks, libraries, file paths, or standards "
        "the user did not mention or clearly imply.\n"
        "- Treat the user's project names, paths, model identifiers, and stated "
        "relationships as immutable evidence. Never reinterpret a project as a "
        "programming language, tool, or owner.\n"
        "- A likely typo may be corrected only when Execution context explicitly names "
        "a verified existing candidate; otherwise preserve it and ask the agent to verify.\n"
        f"- Do NOT invent {absolutes}.\n"
        "- Do NOT end with questions for the user; the agent discovers via tools.\n"
        "- Do NOT mention that you are an AI.\n"
        "Structure (use only the sections inferable from the prompt):\n"
        f"- One-line {task_kw} statement starting with an imperative verb.\n"
        f"- {ctx}: brief inferred situation (only if inferable).\n"
        f"- {obj}: what to achieve.\n"
        f"- {constr}: boundaries (only if inferable).\n"
        f"- {accept}: task-appropriate evidence (source comparison for research/docs; "
        "a runnable check for code changes), only if inferable.\n"
        f"{target_guidance(target, 'rewrite', language)}\n"
        "- Keep it concise (max ~140 words).\n"
        f"- {agent_note}\n"
    )


def _task_before_fenced_code(prompt: str) -> bool:
    """True when the prompt has a task verb BEFORE a fenced code block.

    The LLM rewrites this kind of prompt better when the task follows the
    source code; surfacing the suggestion nudges the caller to reorder.
    """
    if "```" not in prompt or len(prompt) <= 300:
        return False
    if not re.search(r"```[\s\S]+?```", prompt):
        return False
    code_pos = prompt.find("```")
    if code_pos <= 0:
        return False
    return (
        re.search(
            r"\b(implement|create|build|fix|refactor|explica|revisa|arregla)\b",
            prompt[:code_pos],
            re.IGNORECASE,
        )
        is not None
    )


def rule_based_suggestions(prompt: str) -> str | None:
    """Static heuristic suggestions as last-resort fallback."""
    p = prompt.lower()
    suggestions = []

    if re.search(r"\b(skill|agente|subagent|swarm|busca|search|investiga|audit|revisa toda)\b", p):
        if not re.search(
            r"\b(scope|alcance|criterio|formato de salida|output format|presupuesto|budget)\b", p
        ):
            suggestions.append(
                "Define el alcance, el formato de salida esperado y los criterios de éxito para el skill/agente/swarm."
            )

    if re.search(
        r"\b(memory bank|memoria|recuerda|\.memory-bank|activeContext|systemPatterns)\b", p
    ):
        if not re.search(
            r"\b(project|proyecto|topic|tema|decisión|decision|progreso|progress)\b", p
        ):
            suggestions.append(
                "Especifica el proyecto/tema y qué tipo de memoria debe actualizarse (decisión, progreso, contexto activo)."
            )

    if re.search(r"\b(fix|arregla|debug|solve|resuelve|help|check)\b", p):
        has_target = re.search(r"\b(file|archivo|function|función|class|line|línea|error|bug)\b", p)
        has_path = "/" in prompt or "\\" in prompt
        if not has_target and not has_path:
            suggestions.append("Especifica el archivo, función o línea afectada.")

    if re.search(r"\b(create|crear|build|implement|add|genera)\b", p):
        if not any(w in p for w in ["test", "prueba", "error handling", "validación"]):
            suggestions.append("Considera mencionar manejo de errores o validaciones.")

    if re.search(r"\b(refactor|optimiz|improv|mejor|clean)\b", p):
        if not any(w in p for w in ["compat", "break", "test"]):
            suggestions.append("Indica si debe mantener compatibilidad o puede romper cambios.")

    connectors = len(re.findall(r"\b(and|then|also|after|before|después|luego|también)\b", p))
    if connectors >= 2 and "\n" not in prompt:
        suggestions.append("Considera numerar los pasos para mayor claridad.")

    if re.search(r"\b(bug|error|fail|crash|no funciona)\b", p):
        if not any(w in p for w in ["traceback", "log", "mensaje", "stack", "línea"]):
            suggestions.append("Incluye el mensaje de error o traceback si lo tienes.")

    if len(prompt) > 400 and "\n" in prompt:
        if not re.search(
            r"^\s*(task|contexto|context|fuente|source|restricciones|constraints|output|salida|format)\s*[:|\-]",
            prompt,
            re.IGNORECASE | re.MULTILINE,
        ):
            suggestions.append(
                "Estructura con secciones planas: Task / Context / Source / Constraints / Output format."
            )

    if re.search(r"\b(refactor|analyze|analyz|review|revisar|audit)\b", p):
        if not re.search(r"\b(if (unknown|missing)|si (falta|desconocido)|no aplica)\b", p):
            suggestions.append(
                "Define qué debe responder el agente si la fuente de verdad no está disponible."
            )

    if _task_before_fenced_code(prompt):
        suggestions.append(
            "Coloca la tarea DESPUÉS del material fuente para mejor calidad de respuesta."
        )

    if not suggestions:
        return None

    header = (
        "Sugerencias para clarificar el prompt:"
        if "á" in prompt or "é" in prompt or re.search(r"\b(el|la|los|las|es|son)\b", p)
        else "Suggestions to clarify the prompt:"
    )
    return header + "\n- " + "\n- ".join(suggestions)
