"""Output cleaning: bullet trimming, soften absolutes, strip meta-commentary."""

from __future__ import annotations

import re
from typing import Optional

from prompt_improve.shared.config import _ABSOLUTE_REPLACEMENTS
from prompt_improve.features.detect import detect_language


def soften_invented_absolutes(text: str) -> str:
    """Replace invented absolute targets with softer phrasing."""
    for pattern, repl in _ABSOLUTE_REPLACEMENTS:
        text = pattern.sub(repl, text)
    return text


def trim_bullet(line: str, limit: int = 180) -> str:
    """Trim at a natural boundary instead of cutting in the middle of a phrase."""
    if len(line) <= limit:
        return line
    search = line[: limit - 3]
    hard_cuts = [search.rfind(marker) for marker in (". ", "? ", "; ")]
    hard_cut = max(hard_cuts)
    if hard_cut >= 90:
        return search[: hard_cut + 1].rstrip()
    soft_cut = search.rfind(", ")
    if soft_cut >= 90:
        return search[:soft_cut].rstrip() + "..."
    return search.rstrip() + "..."


def remove_long_examples(line: str) -> str:
    shortened = re.sub(r"\s*\((?:por ejemplo|e\.g\.|for example),[^)]*\)", "", line, flags=re.IGNORECASE)
    return shortened if len(shortened) < len(line) else line


def sanitize_bullet(line: str) -> str:
    """Remove over-prescriptive named tool suggestions from LLM output."""
    noisy_tools = r"(OWASP ZAP|Burp Suite|SonarQube|Snyk|Semgrep|Checkmarx)"
    if re.search(noisy_tools, line, re.IGNORECASE):
        if detect_language(line) == "Spanish":
            return "- ¿Qué tipos de pruebas de seguridad y categorías de vulnerabilidad deben cubrirse, y cuáles son los criterios de aceptación?"
        return "- What security test categories and vulnerability classes should be covered, and what are the acceptance criteria?"
    return line


def clean_response(text: str, original: str) -> Optional[str]:
    """Clean a clarify-mode response into 1-3 bullets."""
    text = text.strip()
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"(?is)^.*?done thinking\.\s*", "", text)
    text = re.sub(r"^```[\w]*\n?|```$", "", text, flags=re.MULTILINE).strip()
    text = re.sub(
        r"^(Improved prompt|Prompt mejorado|Sugerencias|Suggestions|Clarifications?):\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    if text.strip().lower() == original.strip().lower():
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullets = []
    for line in lines:
        line = re.sub(r"^\d+[\.\)]\s*", "- ", line)
        if not line.startswith("- "):
            line = f"- {line}"
        line = sanitize_bullet(line)
        if len(line) > 180:
            line = remove_long_examples(line)
        if len(line) > 180:
            line = trim_bullet(line)
        bullets.append(line)
        if len(bullets) >= 3:
            break
    return "\n".join(bullets) if bullets else None


def clean_rewrite(text: str, original: str) -> Optional[str]:
    """Clean a rewrite-mode response into a structured spec."""
    text = text.strip()
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"(?is)^.*?done thinking\.\s*", "", text)
    text = re.sub(r"^```[\w]*\n?|```$", "", text, flags=re.MULTILINE).strip()
    text = re.sub(
        r"^(Here is|Aqu[ií] est[aá]|Sure|Claro|Por supuesto|Rewritten prompt|Prompt reescrito)[:!.]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?is)\n*\*?\*?(?:preguntas de validaci[oó]n|validation questions|preguntas|questions?)\*?\*?\s*:\s*.*\Z",
        "",
        text,
    )
    text = soften_invented_absolutes(text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if len(text) < 20 or text.lower() == original.strip().lower():
        return None
    return text
