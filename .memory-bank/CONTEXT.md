# CONTEXT - Current State
> Updated: 2026-07-23

## What it does
UserPromptSubmit hook that improves vague prompts before the agent sees them:
- **Rewrite** (<260 chars vague) → structured spec; **Clarify** (longer) → 1–3 action bullets
- **Cloud escalation** for hard domains (security/architecture/migration) → DeepSeek V4 Flash
- **Passthrough** for trivial, concrete-path, anaphoric, or already-structured prompts
- **Target-aware shaping** per receiving CLI/model family (incl. **Grok Build**)
- **Deterministic continuation** for bare "continua" (memory expansion, no LLM)
- **Ecosystem skill hints** for known stacks

## Current version
**17.3.0** — cloud-first cache partitioned by provider model; explicit
target diagnostics; DeepSeek R1 vs V3/V4 shaping corrected; Python 3.14
package/CI support.

## Architecture
```
shared/     config, cache, ollama, paths, metrics, compat
features/   detect, classify, improve, clean, rules, hints, ecosystem, target/
command.py  hook entry · cli.py diagnostic subcommands
tests/      improve suite split: routing/cascade/role_model/fallback/messages + _helpers
```
Shim: `~/.claude/hooks/prompt-improve.py` → package (symlink to repo).

## Host (native Ubuntu 26)
- Ollama via system `ollama.service` (systemd-first)
- Improve primary: `cryptidbleh/gemma4-claude-opus-4.6:latest` (round-17)
- PATH tool: `uv tool install -e .` → `prompt-improve==17.3.0`
- Live shim + warmup are symlinks into this repository (verified)

## Blockers / Risks
- None active.
- Refresh `SHAPES` when `~/.claude/rules/model-specific.md` gains failure-modes.
