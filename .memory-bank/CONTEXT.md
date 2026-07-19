# CONTEXT - Current State
> Updated: 2026-07-18

## What it does
UserPromptSubmit hook that improves vague prompts before the agent sees them:
- **Rewrite** (<260 chars vague) → structured spec; **Clarify** (longer) → 1–3 action bullets
- **Cloud escalation** for hard domains (security/architecture/migration) → DeepSeek V4 Flash
- **Passthrough** for trivial, concrete-path, anaphoric, or already-structured prompts
- **Target-aware shaping**: format + behavior per receiving CLI/model family
- **Deterministic continuation** for bare "continua" (memory expansion, no LLM)
- **Ecosystem skill hints** for known stacks (Angular, React, K8s, Foundry, …)

## Current version
**17.2.0** — Grok Build is a first-class target family; Ollama improve tail excludes embeddings.

## Architecture
```
shared/     config, cache, ollama, paths, metrics, compat
features/   detect, classify, improve, clean, rules, hints, ecosystem, target/
command.py  hook entry · cli.py diagnostic subcommands
```
Shim: `~/.claude/hooks/prompt-improve.py` → package (symlinked to repo).

## Host (native Ubuntu 26)
- Ollama via **system** `ollama.service` (systemd-first autostart; nohup only if no unit)
- Improve primary: `cryptidbleh/gemma4-claude-opus-4.6:latest` (round-17)
- Target families: Claude, Codex/GPT, Gemini, Qwen, DeepSeek, GLM, MiniMax, Kimi, MiMo, Gemma, **Grok**, generic

## Blockers / Risks
- Behavior mitigations are static text from `~/.claude/rules/model-specific.md` — refresh when that rule changes.
- Shared `user-prompt-pipeline.py` controller list may omit `grok`; package still detects via `GROK_AGENT`.
