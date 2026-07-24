# Reliability, cache, diagnostics, and packaging plan

> Date: 2026-07-23
> Status: implemented and validated

## Goal

Improve the highest-value gaps found in the `prompt-improve` runtime and its
local integration without widening authority into credentials, deployments, or
unrelated global tooling.

## Confirmed baseline

- `main` is clean and matches `origin/main`.
- 266 tests pass, one live Ollama smoke test is skipped, and coverage is 82.46%.
- Ruff, Ruff format, Pyright/codescan, pip dependency checks, and shellcheck pass.
- The live Claude shim and warmup script are symlinks to this repository.
- Claude and Codex both invoke the shared `user-prompt-pipeline.py`.

## Planned changes

1. Cache successful cloud improvements in the normal routing path so repeated
   hard prompts avoid unnecessary network cost and latency.
2. Correct DeepSeek shaping so R1 remains a reasoner-specific profile while
   V3/V4 guidance no longer labels all DeepSeek models as reasoning models.
3. Add explicit `--cli` and `--model` overrides to the `target` and `improve`
   diagnostic commands.
4. Align packaging and CI with the locally validated Python 3.14 runtime and
   make the test extra self-contained for type checking/build validation.
5. Complete user-facing runtime/diagnostic documentation and replace the
   placeholder code-architecture memory with verified project facts.

## Implementation slices

### 1. Cloud-route cache

- File: `src/prompt_improve/features/improve.py`.
- Preserve the existing local-call cache behavior.
- In the hard/cloud-first branch, look up the target-specific mode key before
  invoking cloud and persist only a successful cleaned cloud result.
- Keep the stored source (`cloud:<model>`) so cache hits remain observable and
  compatible with existing output framing.
- Test in `tests/test_improve_routing.py` with an isolated cache directory:
  first call invokes cloud, second call returns the same result without cloud.

### 2. DeepSeek lineage shaping

- File: `src/prompt_improve/features/target/shape.py`.
- Make the shared DeepSeek layer neutral across instruct and reasoner lineages:
  concise/self-contained task, observable output contract, no hidden CoT.
- Keep R1's existing zero-shot/no-system-prompt/temperature variant.
- Label V3/V4 variants as instruct/agentic instead of applying the blanket
  "reasoning model" claim.
- Extend `tests/test_target.py` so V4 includes instruct guidance while R1 does
  not inherit it.

### 3. Target-aware diagnostics

- File: `src/prompt_improve/cli.py`.
- Add `--cli` and `--model` to both `target` and `improve`.
- Convert these arguments to the same payload fields consumed by
  `target_profile_from_request`; do not create a second classifier.
- Extend `tests/test_cli.py` with explicit provider-through-CLI precedence and
  `improve` forwarding coverage.
- Update the top-level help in `src/prompt_improve/command.py`.

### 4. Packaging and CI

- Files: `pyproject.toml`, `.github/workflows/ci.yml`, `LICENSE`.
- Add the already locally exercised Python 3.14 classifier and CI matrix entry.
- Put `mypy` and `build` in the test extra so one documented install provides
  every CI quality tool.
- Build a wheel and smoke the installed console command in CI.
- Use an SPDX license expression plus the tracked MIT license file, subject to
  a local wheel-build validation.

### 5. Documentation and durable context

- File: `README.md`: document the real `uv tool` install path, cloud/cache/
  metrics/autostart/target overrides, and new diagnostic flags.
- File: `.memory-bank/topics/code-architecture.md`: replace unrelated template
  symbols and conventions with verified module boundaries and hot paths.
- Refresh `.memory-bank/topics/code-map.md` only after implementation so line
  numbers and symbols describe the final tree.
- Update current task/progress/decisions with concise durable facts, not logs.

## Risk controls

- No change to live symlink targets or global hook ordering; inspection showed
  the surrounding wiring is already canonical.
- No cloud smoke call, outbound publication, or credential access.
- Cache changes keep the current schema/key and TTL/cap behavior.
- DeepSeek changes are prompt text only and are guarded by exact lineage tests.
- Packaging metadata is accepted only if both sdist and wheel build locally.
- Existing user changes are absent; each slice will be reviewed through
  `git diff` before the full test pass.

## Verification matrix

| Area | Focused check | Final check |
|---|---|---|
| Cloud cache | routing cache regression test | full pytest + coverage |
| Model shaping | DeepSeek target tests | Ruff + full pytest |
| CLI | subprocess target/improve tests | installed command smokes |
| Packaging | local `python -m build` | wheel contents/install smoke |
| Shell/integration | shellcheck warmup | live symlink/cmp checks |
| Repository | focused Ruff on changed Python | Ruff check/format + codescan |

## Acceptance criteria

- Repeated cloud-routed work returns the cached result without a cloud call.
- DeepSeek V4 and R1 guidance are mutually consistent and tested.
- Diagnostic target overrides resolve the same profiles as hook payloads.
- Python 3.11 through 3.14 remain covered by CI metadata/configuration.
- Package build, tests, lint, format, type checks, and focused CLI smokes pass.
- Live hook symlinks remain intact and no secret-bearing configuration is read
  or modified.
