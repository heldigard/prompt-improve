# REFERENCE - Stable Facts

## Improve model chain (round-17 2026-07-13, Ollama)
Source of truth: `shared/config.py::_DEFAULT_IMPROVE_CHAIN` and `~/ollama-bench/RANKING.md`.

| # | Model | Score |
|---|---|---:|
| 1 | `cryptidbleh/gemma4-claude-opus-4.6:latest` | 2.97 |
| 2 | `hf.co/TeichAI/Qwen3.5-9B-Fable-5-v1-GGUF:Q4_K_M` | 2.46 |
| 3 | `hf.co/Jackrong/Negentropy-claude-opus-4.7-9B-GGUF:Q4_K_M` | 2.03 |
| 4 | `SetneufPT/Qwopus3.5-4B-Coder-MTP_Q4_64k_8GB-GPU:latest` | 1.68 |

- Overrides: `OLLAMA_IMPROVE_MODELS`, `OLLAMA_IMPROVE_ROLE_PROMPT_{REWRITE,CLARIFY}`
- Available-model tail **excludes** embedding tags (`nomic-embed-*`, `bge-*`, `embedding*`)
- OmniCoder demoted to bug_finding/pdf_extract depth (not in improve chain)

## Target model fleet (detection, not improver)
| Family | Example IDs / CLI |
|---|---|
| Claude | opus/sonnet/fable/haiku · `CLAUDECODE`, `transcript_path` |
| OpenAI/Codex | gpt-5.x · `CODEX_MODEL` |
| Gemini | Gemini 3.x · antigravity |
| Grok | grok-4.5 · `GROK_AGENT`, `GROK_MODEL`, `XAI_MODEL` |
| Proxies | MiniMax, Kimi, DeepSeek, GLM, Qwen, MiMo |

## Dependencies
- `ollama_client` + `cheap_llm` via `shared/compat.py` (`~/.claude/scripts/`)

## Commands
```bash
pip install -e ~/prompt-improve
cd ~/prompt-improve && .venv/bin/python -m pytest tests/ -q
prompt-improve detect --prompt "fix foo.py"
prompt-improve target   # under Grok: family=grok
```

## Key env
| Var | Role |
|---|---|
| `OLLAMA_IMPROVE_TOTAL_TIMEOUT` | Shared wall budget (default 20s) |
| `OLLAMA_IMPROVE_TIMEOUT` | Per primary attempt (default 45s) |
| `OLLAMA_IMPROVE_CACHE_TTL` / `CACHE_MAX_ENTRIES` | Cache TTL + size cap |
| `PROMPT_IMPROVE_TARGET_CLI` / `_MODEL` | Explicit target override |
| `PROMPT_IMPROVE_SHAPE_BY` | `model` (default) \| `cli` |
| `GROK_AGENT` / `GROK_MODEL` / `XAI_MODEL` | Grok Build detection |
| `OLLAMA_IMPROVE_METRICS=1` | Stderr counters |

## Related
- `~/codeq/`, `~/smart-trim/`, `~/ollama-bench/`
