# Progress

## 2026-07-19
- CLI: `--help` documents improve/detect/classify/target; `SystemExit` propagates subcommand exit codes.
- Tests: split former `test_improve` monolith into routing/cascade/role_model/fallback/messages + `_helpers` (incl. `_FAKE_REWRITE`).
- Package reinstalled: `prompt-improve==17.2.0` via `uv tool install -e .`.
- Validation: full pytest + ruff green.

## 2026-07-18
- **v17.2.0 Grok target family**: detection + GFM/yolo shape + 4.5 variant.
- Embedding tail filter (nomic/bge/embedding* never selected).
- Native Ubuntu Ollama: systemd-first; ecosystem hints → `features/ecosystem.py`.
- Validation: 262 pytest, ruff clean.

## 2026-07-15
- Diagnostic CLI subcommands; shared 20s total timeout; memory-bank path safeguards; CI 3.11–3.13 + cov≥80%.

## 2026-07-14 … 07-09
- Cache size cap, metrics, shape-by env, rules labeling, DeepSeek-R1 lineage; target profiles vertical slice; rewrite acceptance contract.

## 2026-07-04
- Graduated monolith → package; role-based routing; public GitHub `heldigard/prompt-improve`.
