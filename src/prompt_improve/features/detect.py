"""Language, trivial, concrete target, and mode detection."""

from __future__ import annotations

import os
import re

from prompt_improve.shared.config import (
    _CONCRETE_ACTION_RE,
    _CONCRETE_FILE_RE,
    REWRITE_THRESHOLD,
    TASK_VERBS_RE,
)
from prompt_improve.shared.paths import _BARE_CONTINUATION_RE

_CONVERSATION_CONTEXT_RE = re.compile(
    r"\b(?:what we (?:discussed|talked about|mentioned)|as (?:discussed|mentioned)|"
    r"that (?:issue|thing) we discussed|lo que (?:hablamos|discutimos|mencion[eé]|mencionamos)|"
    r"como (?:dijimos|hablamos|discutimos)|eso que (?:hablamos|mencion[eé]))\b",
    re.IGNORECASE,
)


# Markers ship in BOTH accented and unaccented forms: a user typing "que quieres"
# or "configuracion" (no accent) would be missed if we only listed "qué" /
# "configuración". Word boundaries are mandatory: substring matching classified
# English prompts containing request/query/unique/sequence ("que") as Spanish.
_SPANISH_MARKER_RE = re.compile(
    r"\b(?:arregla|revisa|corrige|continua|implementa|mejora|mejorar|prueba|pruebas|"
    r"casos|funcione|archivo|configuracion|configuración|seguridad|crea|crear|"
    r"que|qué|como|cómo)\b",
    re.IGNORECASE,
)

# Native Claude Code prompt classification emits XML-style blocks. When the
# user prompt already contains one of these tags, prompt-improve should NOT
# rewrite it: the native classifier has already shaped the prompt and a
# second rewrite would dilute the structure. Detection requires a CLOSING
# tag (`<task>...</task>`) so a half-typed or single-tag prompt does not
# trigger the gate. The list mirrors the tags Claude's classifier actually
# emits today (task/objective/context/constraints/acceptance).
_NATIVE_CLAUDE_XML_RE = re.compile(
    r"<(?:task|objective|context|constraints|acceptance)>[\s\S]+?</"
    r"(?:task|objective|context|constraints|acceptance)>",
    re.IGNORECASE,
)


def detect_language(prompt: str) -> str:
    """Heuristic Spanish/English detector. Both accented and unaccented markers match."""
    if _SPANISH_MARKER_RE.search(prompt) or re.search(r"[áéíóúñ¿¡]", prompt):
        return "Spanish"
    return "English"


def has_concrete_target(prompt: str) -> bool:
    """True when the user already supplied enough scope for the large model.

    Rewriting an actionable prompt with a smaller local model can only lose
    evidence. Paths, repository-style identifiers, or an explicit outcome
    clause are sufficient when paired with an action verb.

    A native Claude XML block (e.g. ``<task>...</task>`` from the runtime
    classifier) also counts as a concrete target — the prompt is already
    shaped and a second rewrite would dilute the structure. Closing tags
    are required so a half-typed tag does not silently passthrough.
    """
    if _NATIVE_CLAUDE_XML_RE.search(prompt):
        return True
    if not _CONCRETE_ACTION_RE.search(prompt):
        return False
    has_path = bool(_CONCRETE_FILE_RE.search(prompt)) or "/" in prompt or "\\" in prompt
    has_repo_name = bool(re.search(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", prompt, re.IGNORECASE))
    has_explicit_outcome = bool(
        len(prompt.split()) >= 8
        and re.search(
            r"\b(?:para\s+(?:saber|establecer|identificar|encontrar|corregir|"
            r"mejorar|verificar|determinar)|so that|in order to|to (?:find|identify|"
            r"determine|verify|establish|fix|improve))\b",
            prompt,
            re.IGNORECASE,
        )
    )
    return has_path or has_repo_name or has_explicit_outcome


def depends_on_conversation_context(prompt: str) -> bool:
    """Return whether only the downstream model can resolve the reference.

    The submit hook receives the current prompt and cwd, not the conversation
    transcript. Rewriting these prompts locally would discard evidence that is
    still available to the large model consuming the original prompt.
    """
    return bool(_CONVERSATION_CONTEXT_RE.search(prompt))


def detect_trivial(prompt: str) -> bool:
    p = prompt.strip().lower()
    if not p:
        return True
    if _BARE_CONTINUATION_RE.match(p):
        return False
    trivial_exact = [
        r"^(ok|okay|o[kK]?|thanks?|thank you|gracias|got it|done|listo|vale|yes|no|yep|nope|sure|cool|great|perfect|genial|perfecto)([!\.\s]+(ok|okay|thanks?|gracias|listo|vale|done|yes|no))*[!\.\s]*$",
        r"^(hi|hello|hey|bye|goodbye|hola|chao|adios|adiós)[!\.\s]*$",
        # Slash-commands: bare or with args. re.match() is prefix-only so
        # "/commit the changes" matches — the downstream CLI handles args;
        # rewriting locally would discard the user's intent.
        r"^/(commit|git|review|plan|refactor|help|setup|resume|clear|compact|status)",
    ]
    if any(re.match(t, p) for t in trivial_exact):
        return True
    if (
        len(p) < 24
        and not re.search(r"[\/\\]", p)
        and not re.search(r"\.(py|ts|tsx|js|jsx|java|go|rs|rb|json|toml|yml|yaml|md)\b", p)
        and not TASK_VERBS_RE.search(p)
    ):
        return True
    return len(p) < 6


def decide_mode(prompt: str) -> str:
    """auto -> rewrite short prompts, clarify long ones. Explicit override wins."""
    mode = os.environ.get("OLLAMA_IMPROVE_MODE", "auto").strip().lower()
    if mode in ("rewrite", "clarify"):
        return mode
    return "rewrite" if len(prompt) < REWRITE_THRESHOLD else "clarify"
