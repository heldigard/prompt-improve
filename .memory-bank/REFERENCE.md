# REFERENCE - Stable Facts

## Model benchmarks (2026-07-05 re-bench — improve task, Ollama 0.31.1, round-3 update)
- Primary: **hf.co/kai-os/Grug-12B-GGUF:Q4_K_M** (improve #1; gemma4-12B compact-reasoning fine-tune, won improve by 2× on hard prompts: 8.39 vs 4.15 over pegasus912). Matches `shared/config.py::_DEFAULT_IMPROVE_CHAIN` + `~/ollama-bench/RANKING.md`. See `~/ollama-bench/.memory-bank/topics/candidates-round-3-2026-07-05.md`.
- #2: **hf.co/pegasus912/gemma-4-12b-it-qat-heretic-ud-q4-k-xl:latest** (improve #2; demoted 2026-07-05; same gemma4-12B family, kept as fallback for diversity)
- #3: **Librellama/gemma4:e2b-Uncensored** (improve #3 + codeq_sum #1)
- Anchor fallback: **qwen3.5:4b** (universal — last in chain, always works)
- Chain in code: `Grug-12B → pegasus912 → Librellama/gemma4:e2b → qwen3.5:4b` (all installed). Full available-model tail appended at runtime by `choose_ollama_model_for_role`; missing models degrade gracefully.
- Superseded: `Huihui-gemma-4-12B-abliterated` (was primary in the OLD `~/bench/ollama/` bench; ranked outside top-5 in the 2026-07-04 re-bench and REMOVED from the host lineup — no longer a safe default). `MobiusDevelopment/gemma-4-12B-it-qat` (uninstalled, was codeq default — also superseded).
- Bench source of truth: **`~/ollama-bench/RANKING.md`** (the vertical-slice successor to the old `~/bench/ollama/`).

### Caveat: leak-detector coverage (RESOLVED 2026-07-04)
The OLD `deep_bench.score()` only flagged `<think>`/`thinking process`/refusals — NOT `<|channel>` turn-tokens (Gemma-4 abliterated merges leak `<|channel|>thought<|channel|>` in the answer field), which false-ranked Huihui #1 until validated through the real `clean_rewrite` pipeline.
`ollama_client._strip_think_tags` strips `<|channel>` at runtime (preserved for any future channel-leaking model).
The NEW `~/ollama-bench` scorer now ALSO detects `<|channel>` (added to `LEAK_PATTERNS` + `STRIPPABLE_TAGS`), closing the gap. New bench outputs no longer need the `clean_rewrite` re-check for this pattern.

## Dependencies
- `ollama_client` — shared Ollama wrapper at `~/.claude/scripts/ollama_client.py`
- `cheap_llm` — cloud cascade at `~/.claude/scripts/cheap_llm.py`
- Both bootstrapped via `shared/compat.py` (absolute path, symlink-safe)

## Current target model versions (user-stated, 2026-07-05)
- Claude: **Sonnet 5**, **Opus 4.8**, **Fable 5**
- Codex/OpenAI: **GPT 5.5**, **GPT 5.6**
- Z.AI/GLM: **GLM 5.2 Code**
- Kimi: **Kimi 2.7 Code**
- MiniMax: **MiniMax 3**
- MiMo: **MiMo 2.5 Pro**
- DeepSeek: **DeepSeek V4 Pro**, **DeepSeek V4 Flash**
- Gemini/Antigravity: `agy35-flash` maps to **Gemini 3.5 Flash (High)**. `agy3-pro` is the **Gemini 3.5 Pro (High)** slot and must fall back to Gemini 3.5 Flash until `agy models` exposes Pro.

## Commands
- Install: `pip install -e ~/prompt-improve`
- Test: `cd ~/prompt-improve && python3 -m pytest tests/ -q`
- Lint: `ruff check .` · Format: `ruff format --check .`

## Related projects
- `~/codeq/` — code-fact extraction CLI (same layout pattern)
- `~/smart-trim/` — PreCompact context-compression hook (same layout pattern)
- `~/.claude/hooks/prompt-improve.py` — shim location (settings.json wired path)

## Env vars
- `OLLAMA_IMPROVE_MODELS` — override global model candidates
- `OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE` — override rewrite role models
- `OLLAMA_IMPROVE_ROLE_PROMPT_CLARIFY` — override clarify role models
- `OLLAMA_IMPROVE_CLOUD_INTELLIGENCE=0` — disable hard-prompt cloud escalation
- `OLLAMA_IMPROVE_CLOUD_FALLBACK=0` — disable cloud availability fallback
