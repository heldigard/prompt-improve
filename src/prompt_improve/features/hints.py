"""Project hints and continuation context for prompt improvement."""

from __future__ import annotations

from pathlib import Path

from prompt_improve.features.detect import detect_language
from prompt_improve.features.ecosystem import ecosystem_skill_hint
from prompt_improve.shared.paths import (
    _existing_path_correction,
    _topic_hint,
    project_current_task_line,
    project_hint,
    should_include_task_hint,
)


def project_hint_for_prompt(prompt: str, cwd: str | None, language: str | None = None) -> str:
    """Project anchor used by the LLM prompt improver (cwd + currentTask + topic + skills)."""
    if not cwd:
        return ""
    try:
        root = Path(cwd).expanduser().resolve()
    except (OSError, ValueError):
        root = None
    if should_include_task_hint(prompt):
        base = project_hint(cwd)
    elif root is not None:
        base = f"cwd={Path(cwd).name or cwd}"
    else:
        return ""
    if root is not None:
        hint = _topic_hint(prompt, root)
        if hint:
            base = f"{base}; {hint}"
    path_hint = _existing_path_correction(prompt)
    if path_hint:
        base = f"{base}; {path_hint}"
    skill_hint = ecosystem_skill_hint(prompt, language)
    if skill_hint:
        base = f"{base}; {skill_hint}"
    return base


def continuation_context(prompt: str, cwd: str | None) -> str | None:
    """Deterministic expansion for bare continuation prompts."""
    if not should_include_task_hint(prompt):
        return None
    task = project_current_task_line(cwd, max_chars=500).strip()
    if not task:
        return None
    language = detect_language(prompt)
    if language == "Spanish":
        return (
            "Tarea: Continuar la tarea activa del proyecto.\n\n"
            f"Contexto activo: {task}\n\n"
            "Nota para el agente: usa esta línea sólo como ancla de continuidad; "
            "verifica archivos y estado antes de editar."
        )
    return (
        "Task: Continue the active project task.\n\n"
        f"Active context: {task}\n\n"
        "Agent note: use this line only as the continuity anchor; verify files "
        "and current state before editing."
    )
