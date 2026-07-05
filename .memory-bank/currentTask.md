# Current Task
> Updated: 2026-07-05

## Goal
- Maintain target-aware prompt improvement for Claude Code, Codex, and Antigravity/Gemini — now behavior-aware (per-family failure-mode mitigation, not just format).

## Status — done
- [x] Target profile detection (`features/target/profile.py`)
- [x] Behavior dimension: `FamilyShape` registry with format + behavior per family (`features/target/shape.py`)
- [x] Fixed 6-family collapse: qwen/deepseek/glm/minimax/kimi/mimo now emit DISTINCT guidance
- [x] Regression tests cover all 11 families + behavior keywords + import surface + language-label substitution
- [x] README documents both dimensions (format table + behavior column) and the `target/` architecture
- [x] Vertical-slice refactor shipped (commit 6a53b96): `target.py` → `target/{profile,shape,__init__}.py`

## Status — carried over (stable)
- [x] Shell wrappers `ec53`/`ec54` export `PROMPT_IMPROVE_TARGET_*` explicitly before calling `enhance`
- [x] Antigravity/Gemini mapping: `agy35-flash` -> Gemini 3.5 Flash High; `agy3-pro` -> Gemini 3.5 Pro High slot with Flash fallback

## Next (optional, non-blocking)
- Refresh behavior hints when `~/.claude/rules/model-specific.md` documents new family failure-modes (one-line edit per `SHAPES` entry).
- If a new model family appears in the CLI fleet: add one `SHAPES` entry + one `_looks_like_*` matcher.
