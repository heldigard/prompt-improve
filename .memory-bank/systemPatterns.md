# System Patterns

## Format
- [YYYY-MM-DD]: Decision -> Reason -> Alternative considered

## Decisions
- [2026-07-04]: Vertical-slice layout (shared/ + features/ + command.py) -> Mirrors codeq/smart-trim patterns; cohesion over size -> Flat single-file rejected (1244L monolith)
- [2026-07-04]: Role-based model routing via `_ROLE_MODEL_MAP` -> Best model per task type; extensible via env vars -> Flat candidate list (no task-type awareness)
- [2026-07-04]: `shared/compat.py` for sys.path bootstrap -> Symlink-safe, absolute path resolution -> Relative `__file__` resolution (breaks on symlinks)
- [2026-07-04]: Hook package (shim + pip install -e) -> Preserves wired path in settings.json -> CLI console script (wrong pattern for a hook)
- [2026-07-04]: `# vs-soft-allow` for improve.py nesting -> for/try/if is natural shape of retry loops over model APIs -> Refactoring would reduce readability
