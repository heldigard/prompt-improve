# REFERENCE - Stable Facts

## Model benchmarks (2026-07-04 deep_bench — improve task, validated through clean_rewrite)
- Primary: **hf.co/mradermacher/Huihui-gemma-4-12B-it-qat-q4_0-unquantized-abliterated-GGUF:Q4_K_M** (score 4.5; leaks `<|channel>` tokens, stripped at `ollama_client._strip_think_tags` source)
- #2: **fredrezones55/Qwopus3.5:9b** (2.91, loads clean)
- #3: **jaahas/crow:9b** (2.73, new)
- Anchor fallback: **qwen3.5:4b** (2.19, universal — last in chain, always works)
- Old winners superseded: `MobiusDevelopment/gemma-4-12B-it-qat` (couldn't load during bench — VRAM contention, blob valid), `batiai/gemma4-12b:q4` (quant-loser, was stale default).
- Bench source: `/home/ellama/bench/ollama/RANKING.md` + `deep_bench.py` (5 tasks × 2 prompts; improve/codeq_sum/smart_trim/web_synth/code_gen).

### Caveat: deep_bench leak-detector gap
`deep_bench.score()` only flags `<think>`/`thinking process`/refusals — NOT `<|channel>`. So Huihui false-ranked #1 until validated through the real hook pipeline. Any new bench MUST run outputs through `prompt_improve.features.clean.clean_rewrite` to catch leaks deep_bench misses.

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
