# Active Context

## 2026-07-04
- Graduated from monolith to vertical-slice package
- Bug fix: rewrite-then-clarify fallback now uses clarify framing
- Shim installed at ~/.claude/hooks/improve-prompt.py
- Awaiting user to install more Ollama models for testing
- 2026-07-04: commits y push (default closing step)
- 2026-07-04: este proyecto tiene su propia memory bank (no agent-memory)
- 2026-07-04: HARNESS FIX — `OllamaRequestError`/`OllamaUnavailable` split in shared `ollama_client.py` + `<|channel>` leak strip + prompt-improve fallback chain now survives model-load failures. Default chain = deep_bench winners (Huihui→Qwopus3.5:9b→crow:9b→qwen3.5:4b). 67 tests pass.
- NEXT: adjust `/home/eldi/bench/ollama` improve-bench to run through the REAL prompt-improve pipeline (systemPrompts + clean_rewrite) so rankings reflect the solution, not deep_bench's own scoring.
