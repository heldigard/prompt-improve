# System Patterns

## Format
- [YYYY-MM-DD]: Decision -> Reason -> Alternative considered

## Decisions
- [2026-07-04]: Vertical-slice layout (shared/ + features/ + command.py) -> Mirrors codeq/smart-trim patterns; cohesion over size -> Flat single-file rejected (1244L monolith)
- [2026-07-04]: Role-based model routing via `_ROLE_MODEL_MAP` -> Best model per task type; extensible via env vars -> Flat candidate list (no task-type awareness)
- [2026-07-04]: `shared/compat.py` for sys.path bootstrap -> Symlink-safe, absolute path resolution -> Relative `__file__` resolution (breaks on symlinks)
- [2026-07-04]: Hook package (shim + pip install -e) -> Preserves wired path in settings.json -> CLI console script (wrong pattern for a hook)
- [2026-07-04]: `# vs-soft-allow` for improve.py nesting -> for/try/if is natural shape of retry loops over model APIs -> Refactoring would reduce readability
- [2026-07-04]: Commit + push to `origin/main` is the DEFAULT closing step for verified work in this project (not gated on a per-task explicit request) -> User pref "recuerda commits y push"; remote = github.com/heldigard/prompt-improve; overrides the global "commit/push only when asked" default -> Waiting for explicit ask each time (friction). Still confirm first for hard-to-reverse ops (force-push, history rewrite, visibility change).
- [2026-07-04]: Project facts/conventions live in THIS `.memory-bank/` (cross-CLI: Claude/Codex/Gemini), NOT in `~/.claude/projects/.../memory/` (Claude-agent-only) -> User reminder "este proyecto tiene su propia memory bank"; keeps Codex/Gemini in sync -> Claude agent-memory dir (invisible to other CLIs)
