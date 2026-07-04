"""Language, trivial, concrete target, and mode detection."""

from __future__ import annotations

import os
import re
from typing import Optional

from prompt_improve.shared.config import (
    TASK_VERBS_RE,
    _CONCRETE_FILE_RE,
    _CONCRETE_ACTION_RE,
    REWRITE_THRESHOLD,
)
from prompt_improve.shared.paths import _BARE_CONTINUATION_RE


def detect_language(prompt: str) -> str:
    p = prompt.lower()
    spanish_markers = [
        "arregla", "revisa", "corrige", "continua", "implementa",
        "mejora", "mejorar", "prueba", "pruebas", "casos", "funcione",
        "archivo", "configuracion", "configuración", "seguridad",
        "qué", "como", "cómo",
    ]
    if any(marker in p for marker in spanish_markers) or re.search(r"[áéíóúñ¿¡]", p):
        return "Spanish"
    return "English"


def has_concrete_target(prompt: str) -> bool:
    """True when a short prompt already names a concrete file/path AND an action verb."""
    has_path = (
        bool(_CONCRETE_FILE_RE.search(prompt))
        or "/" in prompt
        or "\\" in prompt
    )
    return has_path and bool(_CONCRETE_ACTION_RE.search(prompt))


def detect_trivial(prompt: str) -> bool:
    p = prompt.strip().lower()
    if not p:
        return True
    if _BARE_CONTINUATION_RE.match(p):
        return False
    trivial_exact = [
        r"^(ok|okay|o[kK]?|thanks?|thank you|gracias|got it|done|listo|vale|yes|no|yep|nope|sure|cool|great|perfect|genial|perfecto)([!\.\s]+(ok|okay|thanks?|gracias|listo|vale|done|yes|no))*[!\.\s]*$",
        r"^(hi|hello|hey|bye|goodbye|hola|chao|adios|adiós)[!\.\s]*$",
        r"^/(commit|git|review|plan|refactor|help|setup|resume|clear|compact|status)",
    ]
    if any(re.match(t, p) for t in trivial_exact):
        return True
    if len(p) < 24 and not re.search(r"[\/\\]", p) and not re.search(
        r"\.(py|ts|tsx|js|jsx|java|go|rs|rb|json|toml|yml|yaml|md)\b", p
    ) and not TASK_VERBS_RE.search(p):
        return True
    return len(p) < 6


def decide_mode(prompt: str) -> str:
    """auto -> rewrite short prompts, clarify long ones. Explicit override wins."""
    mode = os.environ.get("OLLAMA_IMPROVE_MODE", "auto").strip().lower()
    if mode in ("rewrite", "clarify"):
        return mode
    return "rewrite" if len(prompt) < REWRITE_THRESHOLD else "clarify"
