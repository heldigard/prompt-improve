# prompt-improve

LLM-powered prompt improvement hook for the local CLI ecosystem. Rewrites vague
prompts into structured specs and clarifies long prompts with actionable bullets.

## Features

- **Role-based model routing**: gemma4-12b for quality, qwen3.5:4b as fallback
- **Target-aware prompt shaping**: detects the receiving CLI/model family and
  shapes the improved prompt in two dimensions — **format** (XML vs Markdown vs
  component blocks) and **behavior** (per-family failure-mode mitigations, e.g.
  Qwen's blind-retry of failed commands, GLM's lost PATH across shell calls,
  MiniMax's exploration loop, Kimi's subagent-model forcing)
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
agent/model that will receive it. Each family gets **two dimensions** of guidance:

- **Format** — how to structure the improved prompt.
- **Behavior** — a mitigation for the family's known failure-mode, sourced from
  `~/.claude/rules/model-specific.md`. Empty for `generic`.

| Family | Format | Behavior mitigation |
|---|---|---|
| **Claude** (Sonnet/Opus/Fable/Haiku) | XML tags `<task>`/`<context>`/`<constraints>`/`<acceptance>` | One imperative objective (avoids over-exploration); separate context from instructions |
| **Codex / OpenAI GPT** | Markdown sections, backticked identifiers, no XML | Structure as FILES / SIGNATURE / STEPS / EDGE CASES / ACCEPTANCE |
| **Antigravity / Gemini** | Component blocks (Objective/Instructions/Context/Output format) | Long context in its own block (avoids focus dilution) |
| **Qwen** | Numbered Markdown, exact paths/flags | Never retry a failed command as-is — change a flag or inspect the error |
| **DeepSeek** | Numbered deterministic steps | Reasoning model — leave room for chain-of-thought |
| **GLM (Z.AI)** | Numbered Markdown, inline env | Persist PATH/env inline per command (GLM loses env across shell calls) |
| **MiniMax** | Agentic Markdown, definition of done | Deliver a minimal first artifact immediately (avoids exploration loop) |
| **Kimi** | Agentic Markdown, single-agent | Don't delegate to subagents (Kimi forces its model on all subagents) |
| **MiMo** | Explicit numbered steps | Number every step; avoid open-ended discretion |
| **Gemma** | Short, flat, strongly labeled | (compact-model constraints are the format) |
| **Generic** | Plain flat Markdown | (none) |

Detection uses hook payload fields first, then environment:
`PROMPT_IMPROVE_TARGET_CLI`, `PROMPT_IMPROVE_TARGET_MODEL`, `ANTHROPIC_MODEL`,
`CLAUDE_AGENT_IDENTITY`, `CODEX_MODEL`, and `AGY_MODEL`. For Codex wrappers,
setting `PROMPT_IMPROVE_TARGET_CLI=codex` and
`PROMPT_IMPROVE_TARGET_MODEL=gpt-5.5` gives deterministic routing.

### Architecture (`features/target/`)

Vertical slice by responsibility — detection (the *how*) is isolated from
prompt-shape knowledge (the *what*):

- `profile.py` — `TargetProfile` + detection/classification (`profile_for_model`,
  `target_profile_from_request`, family matchers, env/payload parsing).
- `shape.py` — `FamilyShape` registry (`SHAPES` dict, one entry per family) with
  format templates + behavior mitigations; `target_guidance()` does dict dispatch.
- `__init__.py` — re-exports the stable public API.

Adding a new family = one `SHAPES` entry + one matcher in `profile.py`.
