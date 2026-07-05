# CONTEXT - Current State
> Updated: 2026-07-04

## What it does
`prompt-improve` is a UserPromptSubmit hook that improves vague prompts before the agent sees them:
- **Rewrite** mode: short/vague prompts (<260 chars) → structured spec
- **Clarify** mode: long prompts → 1-3 action bullets
- **Cloud escalation**: hard prompts (security/architecture/migration) → DeepSeek V4 Flash
- **Deterministic continuation**: bare "continua" → memory-based expansion (no LLM)

## Recent Changes
- 2026-07-04: Graduated from `~/.claude/hooks/prompt-improve.py` (1244L monolith) to `~/prompt-improve/` package
- 2026-07-04: Added role-based model routing (gemma4-12b primary, qwen3.5:4b fallback)
- 2026-07-04: Dropped HauhauCS-4b from default candidates

## Architecture
Vertical-slice layout: `shared/` (infra) + `features/` (domain) + `command.py` (entry).
Shim at `~/.claude/hooks/prompt-improve.py` delegates to the package.

## Blockers / Risks
- None currently.
