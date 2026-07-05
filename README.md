# prompt-improve

LLM-powered prompt improvement hook for the local CLI ecosystem. Rewrites vague
prompts into structured specs and clarifies long prompts with actionable bullets.

## Features

- **Role-based model routing**: gemma4-12b for quality, qwen3.5:4b as fallback
- **Target-aware prompt structure**: detects Claude Code, Codex/OpenAI GPT, and
  Antigravity/Gemini targets and shapes the improved prompt for that model family
- **Cloud escalation**: complex prompts (security, architecture, migration) routed to DeepSeek V4 Flash
- **Language-aware**: detects Spanish/English, preserves user language
- **Project-grounded**: reads `.memory-bank/currentTask.md` for context
- **Deterministic continuation**: bare "continua" prompts get memory-based expansion (no LLM)
- **Cached**: 5-minute TTL cache per project scope and target model profile

## Install

```bash
pip install -e ~/prompt-improve
```

## Test

```bash
cd ~/prompt-improve && python3 -m pytest tests/ -q
```

## How it works

The hook fires on every user prompt via `~/.claude/settings.json` (UserPromptSubmit)
and can also be called directly as `python3 ~/.claude/hooks/prompt-improve.py "prompt"`.
It classifies the prompt, selects the best local model, and either:
- **Rewrites** short/vague prompts (<260 chars) into structured specs
- **Clarifies** longer prompts with 1-3 action bullets

If the local Ollama daemon is down, it falls back to a cloud cascade (Ling).
If the prompt is hard (security/architecture/migration), it escalates to DeepSeek V4 Flash.

## Target profiles

The local Ollama model improves the prompt, but the output is optimized for the
agent/model that will receive it:

- **Claude / Sonnet 5 / Opus 4.8 / Fable 5 / Haiku**: XML-style sections such as
  `<task>`, `<context>`, `<constraints>`, and `<acceptance>`.
- **Codex / OpenAI GPT 5.5 / GPT 5.6**: clean Markdown sections with explicit workflow,
  tool-use, verification, and backticked code identifiers.
- **Antigravity / Gemini 3.5 Flash / Gemini 3.5 Pro**: component blocks such
  as Objective, Instructions, Context, Constraints, and Output format.
- **Proxy models** (`GLM 5.2 Code`, `Kimi 2.7 Code`, `MiniMax 3`,
  `MiMo 2.5 Pro`, `DeepSeek V4 Pro`, `DeepSeek V4 Flash`, `Qwen`): direct
  Markdown with literal steps and minimal implicit intent.

Detection uses hook payload fields first, then environment:
`PROMPT_IMPROVE_TARGET_CLI`, `PROMPT_IMPROVE_TARGET_MODEL`, `ANTHROPIC_MODEL`,
`CLAUDE_AGENT_IDENTITY`, `CODEX_MODEL`, and `AGY_MODEL`. For Codex wrappers,
setting `PROMPT_IMPROVE_TARGET_CLI=codex` and
`PROMPT_IMPROVE_TARGET_MODEL=gpt-5.5` gives deterministic routing.
