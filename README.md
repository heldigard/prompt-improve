# prompt-improve

LLM-powered prompt improvement hook for Claude Code. Rewrites vague prompts into
structured specs and clarifies long prompts with actionable bullets.

## Features

- **Role-based model routing**: gemma4-12b for quality, qwen3.5:4b as fallback
- **Cloud escalation**: complex prompts (security, architecture, migration) routed to DeepSeek V4 Flash
- **Language-aware**: detects Spanish/English, preserves user language
- **Project-grounded**: reads `.memory-bank/currentTask.md` for context
- **Deterministic continuation**: bare "continua" prompts get memory-based expansion (no LLM)
- **Cached**: 5-minute TTL cache per project scope

## Install

```bash
pip install -e ~/prompt-improve
```

## Test

```bash
cd ~/prompt-improve && python3 -m pytest tests/ -q
```

## How it works

The hook fires on every user prompt via `~/.claude/settings.json` (UserPromptSubmit).
It classifies the prompt, selects the best local model, and either:
- **Rewrites** short/vague prompts (<260 chars) into structured specs
- **Clarifies** longer prompts with 1-3 action bullets

If the local Ollama daemon is down, it falls back to a cloud cascade (Ling).
If the prompt is hard (security/architecture/migration), it escalates to DeepSeek V4 Flash.
