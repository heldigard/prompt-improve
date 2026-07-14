# Project: prompt-improve

`prompt-improve` — LLM-powered prompt improvement hook for Claude Code (and
Codex/Gemini via symlink). Graduated from the monolithic
`~/.claude/hooks/prompt-improve.py` (1244L) into its own vertical-slice package,
mirroring the `codeq` and `smart-trim` project layouts.

## Architecture: vertical-slice hook package (NOT a CLI)

prompt-improve is a **UserPromptSubmit hook**, not a CLI. Entry point is
`~/.claude/hooks/prompt-improve.py` — a ~20-line **shim** that does only:
`from prompt_improve.command import main; main()`. The hook is wired in
`~/.claude/settings.json`. The shim preserves that wired path.

## Layout

```
src/prompt_improve/
  shared/        config, compat, ollama, ollama_url, cache, paths (infra; no feature deps)
  features/
    detect.py    language, trivial detection, concrete target, mode
    classify.py  hard-prompt signals, domain/intent regex
    improve.py   LLM calls (ollama clarify/rewrite, cloud cascade, router)
    clean.py     output cleaning, bullet trimming, soften absolutes
    rules.py     rule-based suggestions, system prompts
    hints.py     project hints, continuation context
    target/      receiving CLI/model profile + prompt shaping (profile, shape)
  command.py     main() entry point
scripts/
  ollama-warmup.sh   best-effort Ollama warmup (SessionStart + cron)
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
   (cryptidbleh primary round-17 fresh 5-way 2.97, TeichAI/Negentropy/Qwopus/Gemma4 fallbacks by current ranking).
2. **Cloud**: hard-prompt escalation to DeepSeek V4 Flash; availability fallback
   to Ling cascade when Ollama is down.

Override per-role: `OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE`, `OLLAMA_IMPROVE_ROLE_PROMPT_CLARIFY`.
