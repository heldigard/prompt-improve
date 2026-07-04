# REFERENCE - Stable Facts

## Model benchmarks (2026-06-30)
- Prompt rewrite/clarify: **gemma4-12b** (quality winner)
- Fallback: **qwen3.5:4b** (clean budget option)
- HauhauCS-4b: removed (niche uncensored, not for prompt improvement)

## Dependencies
- `ollama_client` — shared Ollama wrapper at `~/.claude/scripts/ollama_client.py`
- `cheap_llm` — cloud cascade at `~/.claude/scripts/cheap_llm.py`
- Both bootstrapped via `shared/compat.py` (absolute path, symlink-safe)

## Commands
- Install: `pip install -e ~/prompt-improve`
- Test: `cd ~/prompt-improve && python3 -m pytest tests/ -q`
- Lint: `ruff check .` · Format: `ruff format --check .`

## Related projects
- `~/codeq/` — code-fact extraction CLI (same layout pattern)
- `~/smart-trim/` — PreCompact context-compression hook (same layout pattern)
- `~/.claude/hooks/improve-prompt.py` — shim location (settings.json wired path)

## Env vars
- `OLLAMA_IMPROVE_MODELS` — override global model candidates
- `OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE` — override rewrite role models
- `OLLAMA_IMPROVE_ROLE_PROMPT_CLARIFY` — override clarify role models
- `OLLAMA_IMPROVE_CLOUD_INTELLIGENCE=0` — disable hard-prompt cloud escalation
- `OLLAMA_IMPROVE_CLOUD_FALLBACK=0` — disable cloud availability fallback
