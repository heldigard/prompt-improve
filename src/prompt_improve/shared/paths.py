# vs-soft-allow: nesting_depth — max indent is 12 spaces (depth 3, within limit); hook miscounts due to flat guard clauses
"""Project memory discovery: currentTask.md, .memory-bank/ hints."""

from __future__ import annotations

import importlib.util
import re
from datetime import UTC, date, datetime
from difflib import get_close_matches
from pathlib import Path
from typing import Any

_PROJECT_MEMORY: Any = None

_ACTIVE_STATUS_RE = re.compile(
    r"\b(active|wip|live|in[- ]?progress|activo|en curso)\b",
    re.IGNORECASE,
)
_HISTORICAL_TASK_RE = re.compile(
    r"\b(history|hist[oó]rico|complete|completed|done|shipped|merged|closed|finished|"
    r"archive|archived|old|viejo|terminad[oa]|completad[oa]|finalizad[oa])\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_BARE_CONTINUATION_RE = re.compile(
    r"^\s*(?:"
    r"continua|contin[uú]a|continue|resume|retoma|sigue|seguimos|"
    r"keep going|go on|"
    r"contin[uú]a\s+(?:por favor|donde ibas|con lo anterior|lo anterior)|"
    r"continue\s+(?:please|where you left off|the previous|from before)"
    r")\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_NO_ACTIVE_TASK_RE = re.compile(
    r"\b(?:sin tarea .*activa|no active task|no current task|no hay tarea .*activa)\b",
    re.IGNORECASE,
)
_COMPLETED_HEADING_RE = re.compile(
    r"^#{1,4}\s+.*\b(?:completed|complete|terminad[oa]|completad[oa]|finalizad[oa])\b",
    re.IGNORECASE | re.MULTILINE,
)
_CHECKED_TASK_RE = re.compile(r"^\s*[-*]\s+\[[xX]\]\s+")
_UNCHECKED_TASK_RE = re.compile(r"^\s*[-*]\s+\[\s\]\s+")
_HOME_PATH_RE = re.compile(r"~/[^\s`'\"<>|]+")


def _load_project_memory() -> Any:
    global _PROJECT_MEMORY
    if _PROJECT_MEMORY is not None:
        return _PROJECT_MEMORY
    path = Path.home() / ".claude" / "scripts" / "project-memory.py"
    spec = importlib.util.spec_from_file_location("project_memory_for_prompt_improver", path)
    if spec is None or spec.loader is None:
        return None
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return None
    _PROJECT_MEMORY = module
    return module


def _filtered_current_task_text(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    helper = _load_project_memory()
    if helper is not None and hasattr(helper, "filter_lines_for_injection"):
        try:
            lines = helper.filter_lines_for_injection(path.name, lines)
        except Exception:
            pass
    return "\n".join(lines)


def _extract_date_age(clean: str, today: date) -> int | None:
    """Return age in days if the line has a date, else None."""
    match = _DATE_RE.search(clean)
    if not match:
        return None
    try:
        return (today - datetime.fromisoformat(match.group(1)).date()).days
    except ValueError:
        return 0


def _extract_candidate_date(clean: str) -> date:
    """Extract the date from a task line, or return date.min."""
    match = _DATE_RE.search(clean)
    if not match:
        return date.min
    try:
        return datetime.fromisoformat(match.group(1)).date()
    except ValueError:
        return date.min


def _clean_task_line(line: str) -> str:
    """Strip list markers and bold from a task line."""
    clean = re.sub(r"^\s*[-*]\s+", "", line).strip()
    clean = re.sub(r"^\[\s\]\s+", "", clean).strip()
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)


def _parse_task_candidates(task_text: str, max_age_days: int) -> list[tuple[int, date, int, str]]:
    """Parse task lines into (priority, date, index, text) candidates."""
    today = datetime.now(UTC).date()
    no_active = bool(_NO_ACTIVE_TASK_RE.search(task_text))
    completed = bool(_COMPLETED_HEADING_RE.search(task_text))
    in_managed = False
    candidates: list[tuple[int, date, int, str]] = []
    for raw in task_text.splitlines():
        line = raw.strip()
        # Skip blank, heading, comment, and checked-task lines
        if not line or line.startswith("#") or _CHECKED_TASK_RE.match(line):
            continue
        # Track managed block markers
        if line == "<!-- task-guidance:start -->":
            in_managed = True
            continue
        if line == "<!-- task-guidance:end -->":
            in_managed = False
            continue
        if line.startswith("<!--"):
            continue
        clean = _clean_task_line(line)
        has_active = bool(_ACTIVE_STATUS_RE.search(clean))
        # Exclusion guards (flat, early-continue)
        if not clean:
            continue
        if no_active and not has_active:
            continue
        if completed and not (_UNCHECKED_TASK_RE.match(line) or has_active):
            continue
        if _HISTORICAL_TASK_RE.search(clean) and not has_active:
            continue
        age = _extract_date_age(clean, today)
        if age is not None and not has_active and age > max_age_days:
            continue
        if in_managed and clean.lower().startswith(("source:", "plan:", "checklist:")):
            continue
        priority = 2 if has_active else 1
        candidates.append((priority, _extract_candidate_date(clean), len(candidates), clean))
    return candidates


def current_task_hint_line(task_text: str, max_age_days: int = 14) -> str:
    """Return the best active task line from currentTask.md."""
    candidates = _parse_task_candidates(task_text, max_age_days)
    if not candidates:
        return ""
    return max(candidates)[3]


def should_include_task_hint(prompt: str) -> bool:
    """Only use currentTask.md for genuinely context-dependent prompts."""
    p = prompt.strip()
    if not p:
        return False
    return bool(_BARE_CONTINUATION_RE.match(p))


def _find_current_task_file(root: Path) -> Path | None:
    """Walk parents to find the nearest .memory-bank/currentTask.md."""
    for parent in [root, *root.parents]:
        if parent == parent.parent:
            break
        ct = parent / ".memory-bank" / "currentTask.md"
        try:
            exists = ct.exists()
        except OSError:
            continue
        if exists:
            return ct
    return None


def project_current_task_line(cwd: str | None, max_chars: int = 500) -> str:
    if not cwd:
        return ""
    try:
        root = Path(cwd).expanduser().resolve()
    except (OSError, ValueError):
        return ""
    ct = _find_current_task_file(root)
    if ct is None:
        return ""
    return current_task_hint_line(_filtered_current_task_text(ct))[:max_chars]


def project_hint(cwd: str | None) -> str:
    """One-line project anchor (cwd basename + currentTask)."""
    if not cwd:
        return ""
    parts = [f"cwd={Path(cwd).name or cwd}"]
    ln = project_current_task_line(cwd, max_chars=120)
    if ln:
        parts.append(f"currentTask={ln}")
    return "; ".join(parts)


_TOPIC_INDEX_LINE_RE = re.compile(r"^\s*-\s+\[([^\]]+)\]\(([0-9a-zA-Z_\-]+)\.md\)")
# Words ignored when scoring prompt↔topic overlap (too generic to anchor on).
_TOPIC_STOPWORDS = frozenset(
    "the a an of for to in on at with and or topic topics index tbd project "
    "memory bank deep context session agent".split()
)
_OPERATIONAL_TOPIC_SLUGS = frozenset(
    {
        "agent-sessions",
        "foreign-sessions",
        "session-handoffs",
    }
)


def _tokenize_for_topic(prompt: str) -> set[str]:
    """Content tokens (len>=3, lowercased, punctuation-stripped) minus stopwords."""
    return {
        w.lower().strip(".,;:()[]\"'`") for w in prompt.split() if len(w) >= 3
    } - _TOPIC_STOPWORDS


def _topic_hint(prompt: str, root: Path, max_scan: int = 40) -> str:
    """One-line topic pointer from ``topics/_index.md`` via keyword overlap.

    Deterministic + fail-open: no LLM, no embeddings — reads the nearest index,
    scores prompt tokens against each topic's title + description, returns the
    best slug when there is real overlap. Returns ``""`` otherwise so the
    improver gets no spurious anchor. Synergy bridge between prompt-improve and
    agent-memory's deep ``topics/`` layer (the controller reads the slug on
    demand if the overlap is relevant).
    """
    idx = root / ".memory-bank" / "topics" / "_index.md"
    try:
        lines = idx.read_text(encoding="utf-8", errors="ignore").splitlines()[:max_scan]
    except OSError:
        return ""
    prompt_tokens = _tokenize_for_topic(prompt)
    if not prompt_tokens:
        return ""
    best_slug = ""
    best_title = ""
    best_score = 0
    for line in lines:
        match = _TOPIC_INDEX_LINE_RE.match(line)
        if not match:
            continue
        title, slug = match.group(1), match.group(2)
        if slug in _OPERATIONAL_TOPIC_SLUGS:
            continue
        desc = line[match.end() :].lstrip(" \t—-")
        hay = f"{title} {desc}".lower()
        score = sum(1 for tok in prompt_tokens if tok in hay)
        if score > best_score:
            best_score = score
            best_slug = slug
            best_title = title
    if best_score == 0 or not best_slug:
        return ""
    return f"topic={best_slug} ({best_title})"


def _existing_path_correction(prompt: str) -> str:
    """Return a verified close path for one mistyped ``~/...`` reference.

    The model must not guess that ``ollama-bech`` is a language, tool, or file
    inside the current repo when ``~/ollama-bench`` actually exists. Only
    explicit home-relative paths are considered and only an existing sibling
    can become a hint.
    """
    for match in _HOME_PATH_RE.finditer(prompt):
        raw = match.group(0).rstrip(".,;:!?)]}")
        requested = Path.home() / raw.removeprefix("~/")
        try:
            if requested.exists() or not requested.parent.is_dir():
                continue
            names = [entry.name for entry in requested.parent.iterdir()]
        except OSError:
            continue
        close = get_close_matches(requested.name, names, n=1, cutoff=0.8)
        if not close:
            continue
        candidate = requested.parent / close[0]
        try:
            if not candidate.exists():
                continue
        except OSError:
            continue
        shown = f"~/{candidate.relative_to(Path.home())}"
        if match.group(0).endswith("/"):
            shown += "/"
        return f"verified path correction candidate: {raw} -> {shown}"
    return ""


def _ecosystem_skill_hint(prompt: str, language: str | None = None) -> str:
    """Return a short guideline hint if the prompt relates to a registered ecosystem skill.

    Deterministic keyword matching that guides the LLM to structure prompt expansion
    using our local ecosystem's preferred patterns and version requirements.
    """
    p = prompt.lower()
    if language is None:
        spanish_indicators = r"\b(?:que|como|para|con|las?|los?|un?a?s?|es|son|del|en|revisa|crea|arregla|implementa|cómo|continuar|tarea)\b"
        if re.search(spanish_indicators, p):
            language = "Spanish"
        else:
            language = "English"

    is_sp = language == "Spanish"

    # Check Angular
    if re.search(r"\bangular\b|\bng-|\b@angular\b|\bngx-", p):
        return (
            "pauta del ecosistema: Para Angular, usa Angular v22, componentes standalone, signals+zoneless, @if/@for, inject() y Signal Forms."
            if is_sp
            else "ecosystem guideline: For Angular, use Angular v22, standalone, signals+zoneless, @if/@for, inject(), and Signal Forms."
        )
    # Check React
    if re.search(r"\breact\b|\bjsx\b|\btsx\b|\bnextjs\b|\bnext\.js\b", p):
        return (
            "pauta del ecosistema: Para React, usa React 19, Server Components, Actions y useActionState/useOptimistic."
            if is_sp
            else "ecosystem guideline: For React, use React 19, Server Components, Actions, and useActionState/useOptimistic."
        )
    # Check Svelte
    if re.search(r"\bsvelte\b|\bsveltekit\b", p):
        return (
            "pauta del ecosistema: Para Svelte, usa Svelte 5 runes ($state, $derived, $effect, $props) y sintaxis onclick."
            if is_sp
            else "ecosystem guideline: For Svelte, use Svelte 5 runes ($state, $derived, $effect, $props) and onclick event syntax."
        )
    # Check Vue
    if re.search(r"\bvue\b|\bvuejs\b|\bpinia\b|\bnuxt\b", p):
        return (
            "pauta del ecosistema: Para Vue, usa Vue 3.5 Composition API, <script setup> y Pinia."
            if is_sp
            else "ecosystem guideline: For Vue, use Vue 3.5 Composition API, <script setup>, and Pinia."
        )
    # Check Tailwind
    if re.search(r"\btailwind\b|\btailwindcss\b", p):
        return (
            "pauta del ecosistema: Para Tailwind, usa Tailwind CSS v4, motor Oxide y configuración @theme."
            if is_sp
            else "ecosystem guideline: For Tailwind, use Tailwind CSS v4, Oxide engine, and @theme configuration."
        )
    # Check CSS (excluding Tailwind)
    if re.search(r"\bcss\b|\bstyling\b|\bstyle\b|\bestilos\b|\bestilo\b|\bdiseño\b", p):
        return (
            "pauta del ecosistema: Para CSS, usa CSS moderno puro (container queries, :has, @layer, oklch, grid/flex) y evita Tailwind a menos que se pida expresamente."
            if is_sp
            else "ecosystem guideline: For CSS, use modern vanilla CSS (container queries, :has, @layer, oklch, grid/flex) and avoid Tailwind unless explicitly requested."
        )
    # Check Python
    if re.search(r"\bpython\b|\bpy\b|\bfastapi\b|\bsqlalchemy\b|\bpydantic\b", p):
        return (
            "pauta del ecosistema: Para Python, usa tipado estricto (evitar Any), Pydantic v2 y async/await. Captura solo excepciones específicas."
            if is_sp
            else "ecosystem guideline: For Python, use strict type hints (no Any), Pydantic v2, and async/await. Catch only specific exceptions."
        )
    # Check JS/TS
    if re.search(r"\btypescript\b|\bts\b|\bjavascript\b|\bjs\b|\bnode\b|\bnodejs\b", p):
        return (
            "pauta del ecosistema: Para JS/TS, usa ES2023+, ESM, type-safe guards e imports limpios."
            if is_sp
            else "ecosystem guideline: For JS/TS, use ES2023+, ESM, type-safe guards, and clean imports."
        )
    # Check Git/Commit
    if re.search(r"\bgit commit\b|\bcommit message\b|\bgit log\b|\bmensaje de commit\b|\bconvencional\b", p):
        return (
            "pauta del ecosistema: Para git commits, escribe un mensaje de commit convencional (Conventional Commit) que coincida con el skill git-commit."
            if is_sp
            else "ecosystem guideline: For git commits, write a Conventional Commit message matching the git-commit skill."
        )
    # Check Memory Bank
    if re.search(
        r"\bmemory bank\b|\bmemoria\b|\b\.memory-bank\b|\bcurrenttask\b|\bactivecontext\b|\bprogress\.md\b",
        p,
    ):
        return (
            "pauta del ecosistema: Para memoria, actualiza y mantén los archivos de .memory-bank (MEMORY.md, CONTEXT.md, progress.md) usando la estructura del skill agent-memory."
            if is_sp
            else "ecosystem guideline: For memory, update/maintain memory files (MEMORY.md, CONTEXT.md, progress.md) using agent-memory skill structure."
        )
    # Check Spring Boot/JPA
    if re.search(r"\bjpa\b|\bhibernate\b|\bspring boot\b|\bspring-boot\b", p):
        return (
            "pauta del ecosistema: Para Spring Boot/JPA, evita consultas N+1, usa lazy loading y respeta límites transaccionales."
            if is_sp
            else "ecosystem guideline: For Spring Boot/JPA, avoid N+1 queries, use lazy loading, and follow transactional boundaries."
        )
    return ""


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
    skill_hint = _ecosystem_skill_hint(prompt, language)
    if skill_hint:
        base = f"{base}; {skill_hint}"
    return base
