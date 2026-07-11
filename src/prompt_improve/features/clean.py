"""Output cleaning: bullet trimming, soften absolutes, strip meta-commentary."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from prompt_improve.features.detect import detect_language
from prompt_improve.shared.config import _ABSOLUTE_REPLACEMENTS

_PATH_LITERAL_RE = re.compile(r"(?<![\w.])(?:~/|/)[A-Za-z0-9._+@:-]+(?:/[A-Za-z0-9._+@:-]+)*/?")
_UNSUPPORTED_TECH_RE = re.compile(
    r"\b(?:codescan|golang|python|django|fastapi|java|spring(?: boot)?|javascript|"
    r"typescript|react|angular|vue|rust|kubernetes|docker|terraform|postgresql|"
    r"mysql|mongodb|redis|maven|gradle)\b",
    re.IGNORECASE,
)

# Rewrite output is advisory context, not a replacement for the user's request.
# Keep both a word and character contract so a verbose local/cloud response
# cannot consume the controller's context window or be cut mid-specification.
MAX_REWRITE_WORDS = 140
MAX_REWRITE_CHARS = 900


def _technology_tokens(value: str) -> set[str]:
    tokens = {match.group(0).lower() for match in _UNSUPPORTED_TECH_RE.finditer(value)}
    if re.search(
        r"\b(?:(?:written|implemented|coded) in|using|language|stack)\s+Go\b|"
        r"\bGo(?:lang)?\s+(?:code|project|module|package|service|implementation)\b",
        value,
    ):
        tokens.add("go-language")
    return tokens


def _verified_close_path(path: str, originals: set[str]) -> bool:
    candidate = Path(path).expanduser()
    try:
        if not candidate.exists():
            return False
    except OSError:
        return False
    normalized = path.rstrip("/")
    return any(SequenceMatcher(None, normalized, old).ratio() >= 0.8 for old in originals)


def introduces_unsupported_specifics(text: str, original: str) -> bool:
    """Reject model-added stack choices and concrete paths.

    A prompt rewrite may organize evidence, but it must not decide a language,
    framework, quality tool, or filesystem location absent from the user input.
    """
    original_paths = {path.rstrip("/") for path in _PATH_LITERAL_RE.findall(original)}
    for path in _PATH_LITERAL_RE.findall(text):
        if path.rstrip("/") not in original_paths and not _verified_close_path(
            path, original_paths
        ):
            return True
    return not _technology_tokens(text).issubset(_technology_tokens(original))


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
    shortened = re.sub(
        r"\s*\((?:por ejemplo|e\.g\.|for example),[^)]*\)", "", line, flags=re.IGNORECASE
    )
    return shortened if len(shortened) < len(line) else line


def sanitize_bullet(line: str) -> str:
    """Remove over-prescriptive named tool suggestions from LLM output."""
    noisy_tools = r"(OWASP ZAP|Burp Suite|SonarQube|Snyk|Semgrep|Checkmarx)"
    if re.search(noisy_tools, line, re.IGNORECASE):
        if detect_language(line) == "Spanish":
            return "- ¿Qué tipos de pruebas de seguridad y categorías de vulnerabilidad deben cubrirse, y cuáles son los criterios de aceptación?"
        return "- What security test categories and vulnerability classes should be covered, and what are the acceptance criteria?"
    return line


def clean_response(text: str, original: str) -> str | None:
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


def clean_rewrite(text: str, original: str) -> str | None:
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
    if introduces_unsupported_specifics(text, original):
        return None
    text = soften_invented_absolutes(text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if len(text) < 20 or text.lower() == original.strip().lower():
        return None
    # Reject rather than truncate: cutting a path, negation, or acceptance
    # criterion would create a plausible-looking but semantically corrupt spec.
    if len(text) > MAX_REWRITE_CHARS or len(text.split()) > MAX_REWRITE_WORDS:
        return None
    return text
