# Active Context

## 2026-07-04
- Graduated from monolith to vertical-slice package
- Bug fix: rewrite-then-clarify fallback now uses clarify framing
- Shim installed at ~/.claude/hooks/improve-prompt.py
- Awaiting user to install more Ollama models for testing
- 2026-07-04: commits y push (default closing step)
- 2026-07-04: este proyecto tiene su propia memory bank (no agent-memory)
- 2026-07-04: HARNESS FIX — `OllamaRequestError`/`OllamaUnavailable` split in shared `ollama_client.py` + `<|channel>` leak strip + prompt-improve fallback chain now survives model-load failures. Default chain = deep_bench winners (Huihui→Qwopus3.5:9b→crow:9b→qwen3.5:4b). 67 tests pass.
- 2026-07-04: OLLAMA UNIFIED — single WSL server (0.23.2→0.31.1, systemd, runs as eldi, `/home/eldi/.ollama` = 64 models = full union). Windows ollama uninstalled + Windows stores deleted. zfujicute/OmniCoder-Qwen3.5-9B migrated via content-addressed blob copy. GPU contention eliminated. Followup fix: OLLAMA_TIMEOUT 20→45s + chain cap 6 + fallback timeout 30s + harness TimeoutError→continue (cold-load robustness). e2e verified.
- NEXT: extend bench_improve_real.py to a codeq_sum task; pin CODEQ_SUMMARY_MODEL to the real-pipeline winner.
- 2026-07-04: <task-notification> <task-id>a8aa469c8f029699a</task-id> <tool-use-id>call_12ac45aaaf514896adbcf65d</tool-use-id> <output-file>/tmp/claude-1000/-home-eldi-prompt-improve/9404da84-47e8-4a78-8566-73205beef958/tasks/a8aa469c8f029699a.output</output-file> <status>completed</s […] (nota truncada; contexto largo → topics/)
