# Current Task
> Updated: 2026-07-23

## Goal
Audit and improve runtime reliability, target shaping, diagnostics, packaging,
CI, documentation, and surrounding live-hook integration.

## Status
- **DONE** — v17.3.0 implemented and fully validated; ready for commit review.

## Acceptance Criteria
- [x] Cloud-first hard prompts reuse target/provider-specific cache entries
- [x] Cloud opt-out ignores cached cloud output
- [x] DeepSeek R1 and V3/V4 guidance are mutually consistent
- [x] `target` / `improve` accept explicit `--cli` and `--model`
- [x] Python 3.11–3.14 CI, wheel smoke, license metadata
- [x] 272 tests + coverage, Ruff, mypy, shellcheck, codescan green
- [x] Live shim/warmup symlinks and installed `uv tool` are on v17.3.0
- [x] README, architecture map, plan, and memory refreshed

## Optional later
- New fleet family → `SHAPES` + matcher + tests
- Refresh SHAPES from model-specific.md when it changes
