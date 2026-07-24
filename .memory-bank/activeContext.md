# Active Context
> Updated: 2026-07-23

## Handoff
- **v17.3.0** is implemented and installed editable through `uv tool`.
- Hard cloud-first results are cached by project, target profile, and configured
  cloud model; `OLLAMA_IMPROVE_CLOUD_FALLBACK=0` ignores cloud cache.
- Diagnostic `target`/`improve` accept `--cli` and `--model`; explicit flags
  use payload-first precedence without changing hook env-first behavior.
- DeepSeek shared guidance is lineage-neutral; V3/V4 are instruct/agentic and
  R1 retains no-system/zero-shot reasoner constraints.
- Python 3.14 is in metadata/CI; wheel includes MIT license and console entry.

## Verify
```bash
.venv/bin/pytest --cov=prompt_improve --cov-fail-under=80
.venv/bin/ruff check . && .venv/bin/mypy src
.venv/bin/python -m build
prompt-improve target --cli codex --model gpt-5.6-sol
```
