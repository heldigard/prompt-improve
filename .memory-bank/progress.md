# Progress

## 2026-07-04
- Created ~/prompt-improve/ project with vertical-slice layout
- Split 1244L monolith into 12 modules (shared/ + features/ + command.py)
- Added role-based model routing (_ROLE_MODEL_MAP)
- Dropped HauhauCS-4b from default candidates
- Installed shim at ~/.claude/hooks/improve-prompt.py
- 49/49 tests passing
- Logic review: 42/43 OK, 1 bug fixed (rewrite-then-clarify framing)
- Initial git commit + bug fix commit
- 2026-07-04T15:07:01Z | status:completed | session:bf07289a-2a17-4ad6-a0d8-6a8676198d3a | claude: Verify logic correctness after monolith-to-package split
- 2026-07-04T15:40:32Z | 2026-07-04 | Migration fully verified + shipped: created GitHub repo heldigard/prompt-improve (public, matches codeq pattern), pushed all 6 commits, configured origin + upstream. Adopted codeq gitignore policy (.claude/ + uv.lock ignored, memory-bank stays tracked). 31 tests pass.
- 2026-07-04T15:59:32Z | 2026-07-04 | Autonomous review commit bca8683: removed dead code (ordered_ollama_models + choose_ollama_model, both 0 refs), fixed fd leak in _spawn_ollama (extracted helper), applied ruff auto-fixes (PEP 604 types, datetime.UTC, collections.abc.Callable) across 9 files. Protect tests/compat.py shim via per-file-ignores (ruff was silently deleting re-exports). mypy clean, 31 tests pass.
