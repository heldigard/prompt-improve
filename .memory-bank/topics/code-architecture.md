# Code Architecture

> Verified 2026-07-23. Project-specific map for `prompt-improve`.
> Use `codeq map -p .` for current line numbers and full symbol discovery.

## Runtime flow

```text
UserPromptSubmit JSON
  → prompt-improve.py (bootstrap shim)
  → command.main()
      → trivial / worker / concrete / anaphoric passthrough
      → target_profile_from_request()
      → route_and_improve()
          → hard prompt: target+cloud-model cache → cloud → local fallback
          → routine prompt: target cache → local → cloud fallback
      → cleaner → additionalContext JSON
      → metrics.emit() in finally
```

The installed `prompt-improve` command enters `command.main()`. Its diagnostic
subcommands dispatch to `cli.main()`; direct free-text arguments use the same
improvement path as the hook.

## Module map

- `prompt-improve.py` — dependency-free shim and source-tree bootstrap.
- `command.py` — hook contract, passthrough policy, shared deadline, output framing.
- `cli.py` — offline `improve`, `detect`, `classify`, and `target` diagnostics.
- `features/detect.py` — language, trivial/concrete/anaphoric detection and mode.
- `features/classify.py` — conservative hard-domain cloud escalation.
- `features/improve.py` — cache/model routing, Ollama/cloud calls, shared messages.
- `features/clean.py` — model-output acceptance and reasoning/meta cleanup.
- `features/rules.py` — system prompts and deterministic suggestion fallback.
- `features/hints.py` / `ecosystem.py` — bounded project and stack guidance.
- `features/target/profile.py` — target CLI/model detection and family/style labels.
- `features/target/shape.py` — per-family format, variant, and behavior guidance.
- `shared/config.py` — fail-open environment parsing and model registry.
- `shared/cache.py` — atomic project/target-scoped TTL cache with size pruning.
- `shared/ollama.py` — loopback discovery, model selection, systemd-first startup.
- `shared/paths.py` — bounded non-symlinked `.memory-bank` context extraction.
- `shared/metrics.py` / `filelock.py` — optional stderr/JSONL counters.
- `shared/compat.py` — optional `ollama_client` and `cheap_llm` adapters.

## Key symbols

| Symbol | Owner | Contract |
|---|---|---|
| `command.main` | `command.py` | Hook/direct entry; always fails open |
| `_try_improve` | `command.py` | One deadline across rewrite→clarify→rules |
| `route_and_improve` | `features/improve.py` | Hard cloud-first vs routine local-first |
| `_build_messages` | `features/improve.py` | Stable system/user context composition |
| `target_profile_from_request` | `target/profile.py` | Env-first hooks; payload-first diagnostics |
| `target_guidance` | `target/shape.py` | Family format + variant + mitigation |
| `load_cached` / `save_cached` | `shared/cache.py` | Atomic cache with project-memory fingerprint |
| `choose_ollama_model_for_role` | `shared/ollama.py` | Preferred chain then deterministic chat tail |
| `project_hint_for_prompt` | `shared/paths.py` | Safe bounded context selection |

## Dependency boundaries

```text
shared/*                    → stdlib and optional external adapters
features/detect             → shared config
features/target/profile     → stdlib only
features/target/shape       → target profile
features/rules              → detect + target
features/improve            → features + shared infrastructure
command                     → features + metrics/config
cli                         → lazy imports of command/features
```

`shared` must not import feature modules. The one deliberate local import from
`paths` into `detect`-related behavior avoids an import cycle and must remain
function-scoped.

## Conventions and invariants

- Hook failures pass through the original prompt; diagnostics may surface
  programmer errors in tests.
- Optional numeric/URL configuration is total and fail-open at import time.
- The entire improvement attempt shares one absolute wall-clock deadline.
- Cache keys include project scope, memory fingerprint, mode, target profile,
  and (for hard cloud-first routes) the configured cloud model.
- Project memory is untrusted input: bounded reads, no escaping symlinks.
- Target model identity outranks CLI family by default; diagnostic flags use
  payload-first precedence intentionally.
- Model output must pass the cleaner before it is cached or emitted.
- Live Claude shim and warmup paths are symlinks to tracked repository files.
- Tests are split by concern; monkeypatched call sites rely on late binding.
