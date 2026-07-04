# vs-soft-allow: nesting_depth — max indent is 12 spaces (depth 3, within limit); hook miscounts due to flat guard clauses
"""Project memory discovery: currentTask.md, .memory-bank/ hints."""

from __future__ import annotations

import importlib.util
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

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


def _extract_date_age(clean: str, today: date) -> Optional[int]:
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
    today = datetime.now(timezone.utc).date()
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


def _find_current_task_file(root: Path) -> Optional[Path]:
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


def project_current_task_line(cwd: Optional[str], max_chars: int = 500) -> str:
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


def project_hint(cwd: Optional[str]) -> str:
    """One-line project anchor (cwd basename + currentTask)."""
    if not cwd:
        return ""
    parts = [f"cwd={Path(cwd).name or cwd}"]
    ln = project_current_task_line(cwd, max_chars=120)
    if ln:
        parts.append(f"currentTask={ln}")
    return "; ".join(parts)


def project_hint_for_prompt(prompt: str, cwd: Optional[str]) -> str:
    """Project anchor used by the LLM prompt improver."""
    if not cwd:
        return ""
    if should_include_task_hint(prompt):
        return project_hint(cwd)
    try:
        return f"cwd={Path(cwd).name or cwd}"
    except Exception:
        return ""
