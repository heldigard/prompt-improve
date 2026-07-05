# Active Context

## 2026-07-05
- SHIPPED (commit 6a53b96, origin/main): behavior-aware vertical-slice refactor of `features/target`. `target.py` (287L) → `target/{profile,shape,__init__}.py`. Two dimensions per family (format + behavior-mitigation). Fixed 6-family collapse bug. 110 tests pass, ruff+mypy clean. Full decision detail: `systemPatterns.md`.
- NEXT: optional Plan-agent validation still pending in background (non-blocking — design self-supporting). Refresh behavior hints when `model-specific.md` updates.

## 2026-07-04 (recap — full detail in systemPatterns.md)
- Monolith → vertical-slice package; shim at `~/.claude/hooks/prompt-improve.py`.
- Harness robustness: `OllamaRequestError`/`OllamaUnavailable` split + `<|channel>` leak strip + chain survives model-load failures. Default chain = deep_bench winners.
- Ollama unified: single WSL server 0.31.1 (64 models), GPU contention eliminated.
- Convention: commits+push to `origin/main` = default closing step for verified work (not gated per-task; confirm only for force-push/history-rewrite/visibility).
- Convention: project facts live in THIS `.memory-bank/` (cross-CLI), not Claude-agent-only dirs.
