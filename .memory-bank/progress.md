# Progress

## 2026-07-18
- **v17.2.0 Grok target family**: detection (`GROK_AGENT`/`GROK_MODEL`/`x-ai`/cli aliases) + GFM/yolo shape + 4.5 variant. Was falling to `generic` on native Grok sessions.
- **Embedding tail filter**: improve chain never selects nomic/bge/embedding* from `/api/tags`.
- **Native Ubuntu Ollama**: systemd-first autostart (system unit preferred on this host); warmup script aligned. Ecosystem hints extracted to `features/ecosystem.py`.
- Validation: 262 pytest, ruff clean; primary cryptidbleh live on RTX 5080.

## 2026-07-15
- Diagnostic CLI subcommands; shared 20s total timeout; memory-bank path safeguards; shim = symlink SoT; CI 3.11–3.13 + cov≥80%. ~241 tests.

## 2026-07-14
- Hardening: cache size cap, optional metrics, `PROMPT_IMPROVE_SHAPE_BY`, rules never mislabeled as rewrite, DeepSeek-R1 reasoner lineage, env scrub by prefix for target tests.

## 2026-07-13
- Ecosystem skill shaping (stacks + Foundry/Azure Functions later same week). Chain re-bench → cryptidbleh primary (round-17).

## 2026-07-09 … 07-12
- Minimal-authority passthrough; native Claude `transcript_path`; fail-open config; cache prune + atomic write; rewrite acceptance contract (≤140 words / 900 chars).

## 2026-07-05 … 07-08
- Target-aware profiles + `target/` vertical slice (format + behavior); topic-hint bridge; test module split; model-variant notes.

## 2026-07-04
- Graduated monolith → package; role-based routing; public GitHub `heldigard/prompt-improve`.
- 2026-07-19T01:42:11Z | status:completed | session:gen:b5be76ba-6819-40eb-8088-60dcc35c1483 | claude: Refresh `SHAPES` behavior lines when `~/.claude/rules/model-specific.md`...
- 2026-07-19T15:52:02Z | CLI help lists diagnostic subcommands; SystemExit propagates return codes; helpers docstring fixed; uv tool 17.2.0 reinstalled
- 2026-07-19T15:56:24Z | Committed CLI help + SystemExit exit-code fix; package reinstalled at 17.2.0.
