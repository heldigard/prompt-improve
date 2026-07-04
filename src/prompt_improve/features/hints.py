"""Project hints and continuation context for prompt improvement."""

from __future__ import annotations

from prompt_improve.features.detect import detect_language
from prompt_improve.shared.paths import (
    project_current_task_line,
    should_include_task_hint,
)


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
