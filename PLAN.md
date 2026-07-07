# PLAN - Model-aware prompt injection audit

## Objective
Audit and improve the extra prompt context injected around user prompts so it
matches the active CLI/model family as closely as practical without inventing
requirements or making hooks brittle.

## Current Injection State
- `~/.claude/hooks/user-prompt-pipeline.py` merges `additionalContext` in this
  order: `caveman-classify.py`, `prompt-improve.py`,
  `agentic-cycle-router.py`, `prompt-router.py`.
- `~/.claude/hooks/prompt-improve.py` is a shim to this repo. The package emits:
  - `[Prompt expandido: <source>]` for rewrite mode.
  - `[Mejora de prompt: <source>]` for clarify mode.
  - A final guard that the original user intent prevails over the expansion.
- `src/prompt_improve/features/improve.py::_build_messages` composes the system
  and user prompt sent to local/cloud improver models.
- `src/prompt_improve/features/rules.py` defines the generic rewrite/clarify
  system prompts.
- `src/prompt_improve/features/target/profile.py` infers the receiving CLI/model
  from hook payload/env/config.
- `src/prompt_improve/features/target/shape.py` appends per-family format and
  behavior guidance for Claude, OpenAI/Codex, Gemini, Qwen, DeepSeek, GLM,
  MiniMax, Kimi, MiMo, Gemma, and generic.
- `~/.claude/hooks/agentic-cycle-router.py` is a shim to
  `~/cli-orchestration/src/cli_orchestration/hooks/agentic_cycle_router.py`.
- `~/.claude/hooks/prompt-router.py` is a shim to `~/skill-router`.
- `skill-router route --explain` currently injects dynamic routing guidance for
  research/web routing and `codescan` quality sensors for this task.

## Detected Target Models / CLIs
- Codex current config: `~/.codex/config.toml` sets `model = "gpt-5.5"`,
  `model_reasoning_effort = "high"`, `model_verbosity = "medium"`.
- Codex profiles include `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.5`, and
  `MiniMax-M3`.
- Claude config: `~/.claude/settings.json` sets `"model": "opus"`; project docs
  describe Claude default controller as `claude-fable-5[1m]` with `opus[1m]`
  as an alternate.
- Env keys present in this session include provider API keys, `CODEX_CI`,
  `CODEX_THREAD_ID`, and `CODEQ_SUMMARY_MODEL`; no explicit
  `PROMPT_IMPROVE_TARGET_MODEL` is set.

## Risks
- The worktree was dirty before this audit; preserve existing user changes.
- Model guidance changes can regress prompt quality silently, so add focused
  regression tests around detection and generated guidance.
- External hook/router files live outside this repo; only edit them if the issue
  is clearly in the active injection path.
- Prompting guidance changes over time; prefer official/current docs and keep
  code declarative enough to update later.

## Plan
- Map all prompt-injection paths with `rg`/`codeq` and targeted file reads.
- Research current official prompting guidance for OpenAI/Codex, Anthropic
  Claude, Google Gemini, DeepSeek, Qwen, and MiniMax/Kimi where official docs
  are available.
- Update target detection if active model ids or payload fields are missing.
- Update `FamilyShape` guidance to be more model/version-aware while keeping the
  emitted context concise.
- Validate `skill-router`/agentic hooks and patch only if they inject stale or
  non-model-aware context.
- Run focused tests first, then relevant broader tests and `codescan`.

## Acceptance
- Target profile detection recognizes active Codex config and common current
  model ids without collapsing distinct families.
- Generated rewrite/clarify prompts include concise, family-appropriate guidance
  and avoid stale assumptions such as Codex having native LSP.
- The prompt pipeline remains fail-open and keeps original user intent dominant.
- Tests cover any new behavior.
- Memory bank records durable decisions/progress after validation.
