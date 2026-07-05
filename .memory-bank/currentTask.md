# Current Task
> Updated: 2026-07-04

## Goal
- Maintain target-aware prompt improvement for Claude Code, Codex, and Antigravity/Gemini.

## Status
- [x] Target profile implementation present (`features/target.py`)
- [x] Regression tests cover Claude, Codex/OpenAI GPT, Antigravity/Gemini, and proxy shell models
- [x] README documents env overrides and per-family prompt shapes
- [x] Shell wrappers `ec53`/`ec54` export `PROMPT_IMPROVE_TARGET_*` explicitly before calling `enhance`
- [x] Reversed hook-name aliases removed from searched project/config surfaces
- [x] Antigravity/Gemini mapping recorded: `agy35-flash` -> Gemini 3.5 Flash High; `agy3-pro` -> Gemini 3.1 Pro High
