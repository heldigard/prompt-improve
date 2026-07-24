# prompt-improve

LLM-powered prompt improvement hook for the local CLI ecosystem. It preserves
actionable prompts and only rewrites or clarifies genuinely underspecified input.

## Features

- **Role-based model routing**: `cryptidbleh/gemma4-claude-opus-4.6` (evidence-fidelity #1, round-17 2026-07-13 fresh 5-way 2.97) → `TeichAI/Qwen3.5-9B-Fable-5-v1` (round-10 champion demoted to fallback, 2.46) → `Jackrong/Negentropy-claude-opus-4.7-9B` (round-7 held, 2.03) → `SetneufPT/Qwopus3.5-4B-Coder-MTP` (round-17 bench-validated, 1.68). Override the whole chain via `OLLAMA_IMPROVE_MODELS`; per-role via `OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE` / `OLLAMA_IMPROVE_ROLE_PROMPT_CLARIFY`
- **Target-aware prompt shaping**: detects the receiving CLI/model family and
  shapes the improved prompt in two dimensions — **format** (XML vs Markdown vs
  component blocks) and **behavior** (per-family failure-mode mitigations, e.g.
  Qwen's blind-retry of failed commands, GLM's lost PATH across shell calls,
  MiniMax's exploration loop, Kimi's subagent-model forcing)
- **Cloud escalation**: complex prompts (security, architecture, migration) routed to DeepSeek V4 Flash
- **Language-aware**: detects Spanish/English, preserves user language
- **Evidence-grounded**: preserves named projects, paths, model identifiers,
  and relationships; verifies close `~/path` typo candidates before exposing them
- **Minimal authority**: actionable prompts pass through unchanged so a small
  local model cannot dilute the large model's reasoning or invent task scope
- **Tool-neutral shaping**: the receiving CLI chooses tools from its own live
  capabilities; the improver does not prime unrelated tools into the task
- **Deterministic continuation**: bare "continua" prompts get memory-based expansion (no LLM)
- **Cached**: 5-minute TTL cache per project scope and target model profile;
  hard-route cloud entries are also partitioned by the improving cloud model

## Install

> **Ubuntu 26 / PEP 668:** system Python is externally managed. Prefer an
> isolated `uv` tool install for the PATH command, or use a project venv.

```bash
uv tool install --force --editable ~/prompt-improve
```

## Test

```bash
cd ~/prompt-improve
uv venv
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
.venv/bin/python -m build
```

## How it works

The hook fires on every user prompt via `~/.claude/settings.json` (UserPromptSubmit)
through `user-prompt-pipeline.py` and can also be called directly as
`python3 ~/.claude/hooks/prompt-improve.py "prompt"`.
It first passes through prompts that already name a path/repository or explicit
outcome. For genuinely underspecified prompts it selects a local model and either:
- **Rewrites** short/vague prompts (<260 chars) into structured specs
- **Clarifies** longer prompts with 1-3 action bullets

If the local Ollama daemon is down, it falls back to the configured cloud cascade.
If the prompt is hard (security/architecture/migration), it escalates to DeepSeek V4
Flash (override the model with `OLLAMA_IMPROVE_CLOUD_MODEL`, disable escalation with
`OLLAMA_IMPROVE_CLOUD_INTELLIGENCE=0`).

### Runtime configuration

Malformed numeric or URL overrides fall back to safe defaults instead of preventing
the hook from loading.

| Variable | Default | Accepted values |
|---|---:|---|
| `OLLAMA_IMPROVE_MODE` | `auto` | `auto`, `rewrite`, or `clarify` |
| `OLLAMA_IMPROVE_TIMEOUT` | `45.0` | Positive finite seconds per primary model attempt |
| `OLLAMA_IMPROVE_TOTAL_TIMEOUT` | `20.0` | Positive finite seconds shared by the whole cloud/local and rewrite/clarify attempt |
| `OLLAMA_IMPROVE_AUTOSTART` | `1` | `0` disables best-effort Ollama startup |
| `OLLAMA_IMPROVE_MODELS` | benchmarked four-model chain | Comma-separated global model chain |
| `OLLAMA_IMPROVE_ROLE_PROMPT_REWRITE` | global chain | Comma-separated rewrite-specific chain |
| `OLLAMA_IMPROVE_ROLE_PROMPT_CLARIFY` | global chain | Comma-separated clarify-specific chain |
| `OLLAMA_IMPROVE_CLOUD_FALLBACK` | `1` | `0` disables all cloud fallback |
| `OLLAMA_IMPROVE_CLOUD_INTELLIGENCE` | `1` | `0` disables cloud-first hard-prompt routing |
| `OLLAMA_IMPROVE_CLOUD_MODEL` | `deepseek/deepseek-v4-flash` | Cloud model used by hard-prompt routing |
| `OLLAMA_IMPROVE_CACHE_TTL` | `300.0` | Finite seconds; `0` or a negative value disables caching |
| `OLLAMA_IMPROVE_CACHE_MAX_ENTRIES` | `500` | Positive maximum JSON cache entries |
| `OLLAMA_IMPROVE_REWRITE_THRESHOLD` | `260` | Positive base-10 character count |
| `OLLAMA_IMPROVE_DEBUG` | `0` | `1` emits routing diagnostics and metrics to stderr |
| `OLLAMA_IMPROVE_METRICS` | `0` | `1` emits per-invocation counters to stderr |
| `OLLAMA_IMPROVE_METRICS_PERSIST` | `0` | `1` appends counters to a locked JSONL file |
| `OLLAMA_IMPROVE_METRICS_DIR` | `~/.claude/state/prompt-improve` | Metrics directory when persistence is enabled |
| `PROMPT_IMPROVE_TARGET_CLI` | detected | Explicit receiving CLI for hook/wrapper use |
| `PROMPT_IMPROVE_TARGET_MODEL` | detected | Explicit receiving model for hook/wrapper use |
| `PROMPT_IMPROVE_SHAPE_BY` | `model` | `model` or `cli` |
| `OLLAMA_URL` | client default or `http://127.0.0.1:11434` | HTTP loopback URL (`localhost`, `127.0.0.1`, or `::1`) |

Successful cloud-first results use the same project/target-aware cache contract
as local results. The configured `OLLAMA_IMPROVE_CLOUD_MODEL` is part of that
route's key, so changing provider/model never reuses the prior cloud output.

## Target profiles

The local Ollama model improves the prompt, but the output is optimized for the
agent/model that will receive it. Each family gets **three layers** of guidance:

- **Format** — how to structure the improved prompt.
- **Variant** — small notes for current model lines such as GPT-5.6, Gemini 3,
  DeepSeek V4, MiniMax M3, or Kimi K2.7 Code.
- **Behavior** — a mitigation for the family's known failure-mode, sourced from
  `~/.claude/rules/model-specific.md`. Empty for `generic`.

| Family | Format | Behavior mitigation |
|---|---|---|
| **Claude** (Sonnet/Opus/Fable/Haiku) | XML tags `<task>`/`<context>`/`<constraints>`/`<acceptance>` | One imperative objective (avoids over-exploration); separate context from instructions |
| **Codex / OpenAI GPT** | Markdown sections, backticked identifiers, no XML | Outcome-first contract: FILES / CONTRACT / CONSTRAINTS / EVIDENCE / ACCEPTANCE |
| **Antigravity / Gemini** | Component blocks (Objective/Instructions/Context/Output format) | Long context in its own block (avoids focus dilution) |
| **Qwen** | Numbered Markdown, exact paths/flags | Never retry a failed command as-is — change a flag or inspect the error |
| **DeepSeek V3/V4** | Numbered deterministic steps | Instruct/agentic model — define visible steps and final contract |
| **DeepSeek R1/reasoner** | Concise zero-shot user prompt; no system prompt | Do not request visible/hidden CoT or add few-shot examples |
| **GLM (Z.AI)** | Numbered Markdown, inline env | Persist PATH/env inline per command (GLM loses env across shell calls) |
| **MiniMax** | Agentic Markdown, definition of done | Deliver a minimal first artifact immediately (avoids exploration loop) |
| **Kimi** | Agentic Markdown, single-agent | Don't delegate to subagents (Kimi forces its model on all subagents) |
| **MiMo** | Explicit numbered steps | Number every step; avoid open-ended discretion |
| **Gemma** | Short, flat, strongly labeled | (compact-model constraints are the format) |
| **Grok** (xAI Grok Build / grok-4.5) | GitHub-flavored Markdown, one imperative objective, acceptance criteria | YOLO/always-approve: cap scope; prefer reversible local edits; parallelize independent reads |
| **Generic** | Plain flat Markdown | (none) |

Detection uses hook payload fields first, then environment. Explicit model IDs
beat CLI fallback, so `MiniMax-M3` launched through Codex still receives MiniMax
guidance instead of GPT guidance. Common env inputs include
`PROMPT_IMPROVE_TARGET_CLI`, `PROMPT_IMPROVE_TARGET_MODEL`, `ANTHROPIC_MODEL`,
`CLAUDE_AGENT_IDENTITY`, `CODEX_MODEL`, `OPENAI_MODEL`, `GEMINI_MODEL`,
`DEEPSEEK_MODEL`, `QWEN_MODEL`, `KIMI_MODEL`, `MINIMAX_MODEL`, `GROK_MODEL`,
`XAI_MODEL`, and `MODEL_NAME`.
For Codex wrappers, setting `PROMPT_IMPROVE_TARGET_CLI=codex` and
`PROMPT_IMPROVE_TARGET_MODEL=gpt-5.6-terra` gives deterministic routing.
Native Claude Code hooks are recognized from their `transcript_path` payload
field even when active-model metadata is absent. `CLAUDECODE` / `CLAUDE_CODE_*`
remain wrapper fallbacks. Native Grok Build sessions are recognized from
`GROK_AGENT` / `GROK_MODEL` / `XAI_MODEL` (or `PROMPT_IMPROVE_TARGET_CLI=grok`).
The complete improvement attempt shares a 20-second wall-clock budget by default
(`OLLAMA_IMPROVE_TOTAL_TIMEOUT`) across cloud/local routing and the optional
rewrite→clarify retry. This remains below the pipeline child's 22-second ceiling,
so failure can still reach deterministic rules instead of being killed mid-call.

## Diagnostic CLI

```bash
prompt-improve detect --prompt "fix foo.py"
prompt-improve classify --prompt "audit the auth design" --mode rewrite
prompt-improve target --cli codex --model gpt-5.6-sol
prompt-improve improve --prompt "continua" --cwd "$PWD" \
  --cli codex --model gpt-5.6-sol
```

The installed command and `python -m prompt_improve.cli` share the same
subcommands. `improve` uses the hook's deterministic continuation and
rewrite→clarify fallback path rather than a separate approximation.
Each explicit `--cli`/`--model` diagnostic argument wins over its corresponding
inherited target variable; model identity still outranks CLI family. Hook
payloads retain the normal environment-first precedence used by wrappers.

### Architecture (`features/target/`)

Vertical slice by responsibility — detection (the *how*) is isolated from
prompt-shape knowledge (the *what*):

- `profile.py` — `TargetProfile` + detection/classification (`profile_for_model`,
  `target_profile_from_request`, family matchers, env/payload parsing).
- `shape.py` — `FamilyShape` registry (`SHAPES` dict, one entry per family) with
  format templates + variant notes + behavior mitigations; `target_guidance()`
  does dict dispatch and overlays current-model notes.
- `__init__.py` — re-exports the stable public API.

Adding a new family = one `SHAPES` entry + one matcher in `profile.py`.

## Native Linux notes

On Ubuntu with a systemd-managed Ollama unit the hook starts the daemon via
`systemctl` (user unit first, then system) before falling back to a detached
`ollama serve`. The available-model tail used when preferred improve-chain
tags are missing excludes embedding-only models (`nomic-embed-*`, `bge-*`,
`embedding*`) so a miss does not burn the 20s wall-clock budget on a non-chat
tag.

The session-start warmup can be disabled with `PROMPT_IMPROVER_WARMUP=0`; model
preloading alone can be disabled with `PROMPT_IMPROVER_PRELOAD=0`, and
`OLLAMA_IMPROVE_WARM_MODEL` overrides the preloaded tag. The live Claude/Codex
warmup and prompt shim are symlinked to this repository, so the tracked scripts
remain the single source of truth.
