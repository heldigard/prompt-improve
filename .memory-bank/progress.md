# Progress

## 2026-07-05 (target-aware prompt profiles)
- Verified current implementation against the CLI ecosystem: Claude Code shell functions in `.zshrc`, Codex external profiles (`gpt-5.4-mini`, `gpt-5.4`, `gpt-5.5`), and Antigravity/Gemini long-context bridge.
- Confirmed target-aware routing exists in `features/target.py`: Claude -> XML tags, Codex/OpenAI GPT -> Markdown workflow/verification, Gemini/Antigravity -> component blocks, proxy models -> literal explicit steps.
- Added regression tests for primary target families (Claude Opus/Sonnet/Fable, Codex GPT, Antigravity/Gemini) and proxy models (MiniMax, DeepSeek, GLM, Qwen), plus target-specific cache separation.
- Added direct CLI output mode for `python3 ~/.claude/hooks/prompt-improve.py "prompt"` so shell wrappers receive plain improved text, not hook JSON.
- Updated `.zshrc` wrappers `ec53`/`ec54` to set `PROMPT_IMPROVE_TARGET_CLI=codex` and the target GPT model before calling `enhance`.
- Removed reversed hook-name references from config/report surfaces; active hook name is only `prompt-improve.py`.
- Updated Gemini/Antigravity references: `agy35-flash` uses Gemini 3.5 Flash High; `agy3-pro` is the Gemini 3.5 Pro High slot and falls back to Flash until the Pro display name appears.
- Added target-family coverage for GPT 5.6, Kimi 2.7 Code, and MiMo 2.5 Pro.
- Updated README with target profile behavior and env overrides.
- Validation: `python3 -m pytest tests/ -q` passed (96 tests); `ruff check .` passed; `python3 -m py_compile` passed for prompt-improve and touched router/guard scripts; `python3 ~/.claude/scripts/test-cworker-config.py -q` passed (12 checks); `python3 ~/.claude/scripts/test-context-guard-lib.py` passed (35 checks); direct `[NO_IMPROVE]` hook smoke returned plain text.

## 2026-07-04 (codescan migration)
- Migrated `codescan` from `~/.claude/scripts/codescan` (342L standalone) to `~/codescan/` vertical-slice project.
- Cleaned stale `~/.claude/scripts/codeq-model-bench.py` (already in `~/codeq/scripts/`).
- Moved `~/.claude/scripts/update-ctags.sh` → `~/codeq/scripts/`.
- Shims updated: `~/.claude/scripts/codescan` (20L) + `~/.claude/tests/test-codescan.py` (15L).
- All 5 sensors verified, ruff clean, smoke test passed.

## 2026-07-04 (maintenance round — autonomous review session)
- ruff format: 7 files (auto-format.sh had backlog). All clean now.
- Bug fix `features/detect.py::detect_language`: "que" / "configuracion" (no accent) missed Spanish detection. Added unaccented marker variants. +1 regression test.
- Bug fix `features/improve.py::call_cloud_cascade`: narrowed `except Exception` → `(OSError, ValueError, TypeError, KeyError)`. Programmer errors (NameError/AttributeError) now surface. +1 regression test (NameError must raise, not be swallowed).
- Bug fix `features/rules.py::_task_before_fenced_code`: extracted from inline nested logic — was nesting depth 5; helper + guard clauses = depth 2.
- Refactor `features/improve.py`: extracted `_build_messages(mode, prompt, cwd)` shared across call_ollama / call_ollama_rewrite / call_cloud_cascade. ~25 lines of duplicated message-formatting collapsed.
- 4 new end-to-end tests for `command.main()`: NO_IMPROVE passthrough, trivial prompt passthrough, no-model fallthrough, rewrite happy-path. Now exercises the actual hook entry point (not just pieces).
- Total: 73/73 tests passing, ruff check + format clean, vertical-slice guard clean.

## 2026-07-04
- Created ~/prompt-improve/ project with vertical-slice layout
- Split 1244L monolith into 12 modules (shared/ + features/ + command.py)
- Added role-based model routing (_ROLE_MODEL_MAP)
- Dropped HauhauCS-4b from default candidates
- Installed shim at ~/.claude/hooks/prompt-improve.py
- 49/49 tests passing
- Logic review: 42/43 OK, 1 bug fixed (rewrite-then-clarify framing)
- Initial git commit + bug fix commit
- 2026-07-04T15:07:01Z | status:completed | session:bf07289a-2a17-4ad6-a0d8-6a8676198d3a | claude: Verify logic correctness after monolith-to-package split
- 2026-07-04T15:40:32Z | 2026-07-04 | Migration fully verified + shipped: created GitHub repo heldigard/prompt-improve (public, matches codeq pattern), pushed all 6 commits, configured origin + upstream. Adopted codeq gitignore policy (.claude/ + uv.lock ignored, memory-bank stays tracked). 31 tests pass.
- 2026-07-04T15:59:32Z | 2026-07-04 | Autonomous review commit bca8683: removed dead code (ordered_ollama_models + choose_ollama_model, both 0 refs), fixed fd leak in _spawn_ollama (extracted helper), applied ruff auto-fixes (PEP 604 types, datetime.UTC, collections.abc.Callable) across 9 files. Protect tests/compat.py shim via per-file-ignores (ruff was silently deleting re-exports). mypy clean, 31 tests pass.
- 2026-07-04 | status:completed | Fallback-chain robustness + stale-defaults fix. (1) Shared `ollama_client.py`: split `OllamaRequestError` (HTTP 4xx/5xx, model-specific → continue) from `OllamaUnavailable` (daemon down → abort); fixed both `*_fallback` utils; added `<|channel>thought<channel|>` leak strip to `_strip_think_tags`. (2) prompt-improve `_run_ollama_models` catches `OllamaRequestError` → continues. (3) Default chain → deep_bench 2026-07-04 winners (Huihui→Qwopus3.5:9b→crow:9b→qwen3.5:4b), validated through real `clean_rewrite`. +3 regression tests (chain continues / aborts / skips-empty). ruff+mypy clean, 67 tests pass.
- 2026-07-04 | status:completed | Ollama server UNIFICATION + cold-load robustness. Diagnosed two daemons (WSL + Windows) fighting for one GPU = VRAM-contention root cause. WSL was the real server (not Windows as believed). Updated WSL 0.23.2→0.31.1 (fixes LFM + `<|channel>` at source). Migrated the 1 Windows-unique model (zfujicute/OmniCoder-Qwen3.5-9B) via content-addressed blob copy + manifest `from` strip. systemd override (User=eldi, OLLAMA_MODELS=/home/eldi/.ollama/models) — installer default read an empty store. Windows ollama uninstalled + both Windows stores deleted. Built `bench_improve_real.py` (real-pipeline improve bench — supersedes deep_bench's improve column which missed `<|channel>`). Followup timeout fix: OLLAMA_TIMEOUT 20→45, fallback cap 30, chain cap 6, harness TimeoutError→continue. e2e `call_ollama_rewrite` verified on 0.31.1.
- 2026-07-05T19:00:37Z | status:completed | 2026-07-05: Normalized active hook entrypoint references to prompt-improve.py across Claude/Codex/Gemini/Antigravity configs and docs. Verified pytest tests/test_improve_prompt.py, py_compile for hooks, verify-hooks all CLIs, and direct NO_IMPROVE shim smokes.
- 2026-07-05T19:09:22Z | status:completed | 2026-07-05: Second review tightened target-profile docs/tests and live worker configs: Gemini routes now document/use agy35-flash as Gemini 3.5 Flash High and agy3-pro/agy-research as the Gemini 3.5 Pro High slot with Flash fallback; Antigravity-hosted Claude routes now use Opus 4.8 and Sonnet 5; Kimi worker text/routes use Kimi 2.7 Code. Removed active reversed legacy hook-name references from searched surfaces. Validation: pytest full suite, ruff, py_compile, cworker config gate, context guard gate, JSON checks, and direct hook smoke pass.
