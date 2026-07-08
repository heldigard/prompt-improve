# CONTEXT - Current State
> Updated: 2026-07-08

## What it does
`prompt-improve` is a UserPromptSubmit hook that improves vague prompts before the agent sees them:
- **Rewrite** mode: short/vague prompts (<260 chars) → structured spec
- **Clarify** mode: long prompts → 1-3 action bullets
- **Cloud escalation**: hard prompts (security/architecture/migration) → DeepSeek V4 Flash
- **Deterministic continuation**: bare "continua" → memory-based expansion (no LLM)
- **Target-aware shaping**: detects the receiving CLI/model family and shapes the
  improved prompt in two dimensions — **format** + **behavior** (failure-mode mitigation)
- **Topic-hint bridge**: `project_hint_for_prompt` also surfaces a deep-topic pointer
  (`topic=<slug>`) from the nearest `.memory-bank/topics/_index.md` via deterministic
  keyword overlap — no LLM, no embeddings, fail-open. Operational session topics
  are skipped to avoid stale worker-log context.

## Recent Changes
- 2026-07-08: Rewrote `command.main()` input parsing — `--version`/`--help` CLI flags + `use_stdin`/`content_read` logic (direct argv mode no longer blocks on a TTY). Split the monolithic `tests/test_improve_prompt.py` (1881L) into 9 focused per-feature test files. 118 tests pass.
- 2026-07-06: Added topic-hint bridge in `shared/paths.py` (`_topic_hint`); `project_hint_for_prompt` now emits `cwd=…; topic=<slug> (title)` when a topic overlaps the prompt. +6 tests (test_topic_hint.py). 108 total pass.
- 2026-07-05: Refactored `features/target.py` → `features/target/` package (`profile.py` + `shape.py` + `__init__.py`); added behavior dimension; fixed 6-family collapse bug. 110 tests pass.
- 2026-07-04: Graduated from `~/.claude/hooks/prompt-improve.py` (1244L monolith) to `~/prompt-improve/` package
- 2026-07-04: Added role-based model routing (gemma4-12b primary, qwen3.5:4b fallback)
- 2026-07-04: Dropped HauhauCS-4b from default candidates

## Architecture
Vertical-slice layout: `shared/` (infra) + `features/` (domain) + `command.py` (entry).
`features/target/` is itself a vertical slice: `profile.py` (detection — the HOW) +
`shape.py` (FamilyShape registry — the WHAT, dict dispatch) + `__init__.py` (stable
re-exports). Shim at `~/.claude/hooks/prompt-improve.py` delegates to the package.

## Blockers / Risks
- Behavior hints are static text encoded from `~/.claude/rules/model-specific.md`; refresh when that rule updates.
