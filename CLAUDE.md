# Project: prompt-improve

`prompt-improve` — LLM-powered prompt improvement hook for Claude Code (and
Codex/Gemini via symlink). Graduated from the monolithic
`~/.claude/hooks/improve-prompt.py` (1244L) into its own vertical-slice package,
mirroring the `codeq` and `smart-trim` project layouts.

## Architecture: vertical-slice hook package (NOT a CLI)

prompt-improve is a **UserPromptSubmit hook**, not a CLI. Entry point is
`~/.claude/hooks/improve-prompt.py` — a ~20-line **shim** that does only:
`from prompt_improve.command import main; main()`. The hook is wired in
`~/.claude/settings.json`. The shim preserves that wired path.

## Layout

```
src/prompt_improve/
  shared/        config, compat, ollama, cache, paths (infra; no feature deps)
  features/
    detect/      language, trivial detection, concrete target, mode
    classify/    hard-prompt signals, domain/intent regex
    improve/     LLM calls (ollama clarify/rewrite, cloud cascade, router)
    clean/       output cleaning, bullet trimming, soften absolutes
    rules/       rule-based suggestions, system prompts
    hints/       project hints, continuation context
  command.py     main() entry point
```

## Conventions

- **One responsibility per feature folder** (cohesion > size).
- **Late binding** for monkeypatched functions in tests.
- `shared/compat.py` bootstraps `sys.path` for `ollama_client` and `cheap_llm`
  from `~/.claude/scripts/`. Absolute path resolution.

## Commands

- Install (dev): `pip install -e .`
- Test: `python3 -m pytest tests/ -q`
- Lint: `ruff check .` · Format: `ruff format --check .`

## Model routing

Two tiers:
1. **Local** (Ollama): role-based selection via `_ROLE_MODEL_MAP`
   (gemma4-12b primary, qwen3.5:4b fallback).
2. **Cloud**: hard-prompt escalation to DeepSeek V4 Flash; availability fallback
   to Ling cascade when Ollama is down.

Override per-role: `OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE`, `OLLAMA_IMPROVE_ROLE_PROMPT_CLARIFY`.
