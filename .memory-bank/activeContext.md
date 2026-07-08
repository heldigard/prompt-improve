# Active Context

## 2026-07-08
- SHIPPED: `command.main()` input-source rewrite — `--version`/`-v` + `--help`/`-h` CLI flags short-circuit before stdin read; `use_stdin` + `content_read` logic so direct argv mode no longer blocks on a real TTY and empty piped stdin falls through to argv. Hook-runtime JSON path unchanged. (Picked up + finished work a sibling model left mid-edit.)
- SHIPPED: test suite split — monolithic `tests/test_improve_prompt.py` (1881L, 111 tests) → 9 focused files mirroring `features/*` (`test_detect`, `test_clean`, `test_hints`, `test_classify`, `test_improve`, `test_target`, `test_cache`, `test_command`, `test_infra`). Helpers colocated, no conftest. 118 tests pass (111 split + 7 in `test_topic_hint`).
- Gates: 118/118 pytest, ruff check + format clean, py_compile OK. Tree committed + pushed to `origin/main`.

## 2026-07-06
- Shipped fuzzy model name matching fallback helper in `ollama.py` to match local Ollama models regardless of prefix registry URLs/usernames or tag variations. Added unit tests to `test_improve_prompt.py`. Gates: 109/109 tests passed, ruff clean.

## 2026-07-05
- SHIPPED (commit 6a53b96, origin/main): behavior-aware vertical-slice refactor of `features/target`. `target.py` (287L) → `target/{profile,shape,__init__}.py`. Two dimensions per family (format + behavior-mitigation). Fixed 6-family collapse bug. 110 tests pass, ruff+mypy clean. Full decision detail: `systemPatterns.md`.
- NEXT: optional Plan-agent validation still pending in background (non-blocking — design self-supporting). Refresh behavior hints when `model-specific.md` updates.

## 2026-07-04 (recap — full detail in systemPatterns.md)
- Monolith → vertical-slice package; shim at `~/.claude/hooks/prompt-improve.py`.
- Harness robustness: `OllamaRequestError`/`OllamaUnavailable` split + `<|channel>` leak strip + chain survives model-load failures. Default chain = deep_bench winners.
- Ollama unified: single WSL server 0.31.1 (64 models), GPU contention eliminated.
- Convention: commits+push to `origin/main` = default closing step for verified work (not gated per-task; confirm only for force-push/history-rewrite/visibility).
- Convention: project facts live in THIS `.memory-bank/` (cross-CLI), not Claude-agent-only dirs.
