---
title: "fix: Harden import-time configuration fail-open"
type: fix
status: completed
date: 2026-07-12
---

# fix: Harden import-time configuration fail-open

## Enhancement Summary

**Deepened on:** 2026-07-12

**Sections enhanced:** configuration contract, URL boundary, entrypoint parity, tests, and docs

**Research used:** repository research, project-learnings review, SpecFlow, `python-pro`, and
`software-development`

### Key Improvements

1. Defined a compatibility-preserving numeric grammar and non-finite-value behavior.
2. Made URL validation explicit across parse errors, authority extras, ports, and IPv6 rendering.
3. Added clean-process acceptance tests for import, module execution, and the real shim.
4. Preserved the harness-provided Ollama default when `OLLAMA_URL` is absent.

## Overview

Preserve the hook's fail-open contract when environment configuration is malformed. Today,
numeric parsing in `shared/config.py` and port parsing in `shared/ollama_url.py` can raise while
`prompt_improve.command` is being imported, before `command.main()` reaches its exception guard.
The installed console entry point therefore exits with an error, while the shim degrades to a
silent no-op instead of emitting the normal hook response.

The repository is otherwise healthy: 145 tests pass, Ruff format/lint are clean, coverage is 83%,
and `codescan all` reports no security, secret, dead-code, lint, or type findings.

## Problem Statement

The following inputs were reproduced as import failures:

- Non-numeric `OLLAMA_IMPROVE_TIMEOUT`, `OLLAMA_IMPROVE_TOTAL_TIMEOUT`, and
  `OLLAMA_IMPROVE_CACHE_TTL` values.
- Non-integer `OLLAMA_IMPROVE_REWRITE_THRESHOLD` values.
- `OLLAMA_URL` values containing a non-numeric or out-of-range port.
- Malformed bracketed IPv6 URLs.

Additional semantic failures do not raise but violate the intended bounds: `nan` can neutralize the
shared local-model budget and `inf` can prevent cache expiration. Valid IPv6 loopback input is also
serialized without brackets, producing an unusable URL.

## Proposed Solution

1. Add small, deterministic environment-number parsers in `shared/config.py`.
2. Fall back to the established defaults when values are empty, non-numeric, non-finite, or invalid
   for the setting.
3. Preserve the existing cache-disable behavior for any finite TTL `<= 0`; require positive values
   for model timeouts and the rewrite threshold.
4. Make `normalize_ollama_url()` total: no caller-provided string may raise.
5. Continue accepting only HTTP loopback hosts, validate ports, reject URL credentials/query/
   fragment/non-root paths, and serialize IPv6 loopback with brackets. The guarded region must
   cover `urlparse()` plus derived `hostname`, `username`, `password`, and `port` access.
6. Add unit and subprocess regression coverage for invalid and valid configuration paths.

## Technical Approach

### Configuration contract

| Setting | Accepted | Invalid fallback |
|---|---|---|
| `OLLAMA_IMPROVE_TIMEOUT` | finite float `> 0` | `45.0` |
| `OLLAMA_IMPROVE_TOTAL_TIMEOUT` | finite float `> 0` | `24.0` |
| `OLLAMA_IMPROVE_CACHE_TTL` | any finite float; `<= 0` disables cache | `300.0` |
| `OLLAMA_IMPROVE_REWRITE_THRESHOLD` | stripped base-10 integer `> 0` | `260` |
| `OLLAMA_URL` | HTTP loopback, optional port `1..65535`, no authority/path extras | `http://127.0.0.1:11434` |

No arbitrary upper cap will be added: large finite values may be an intentional local override, and
changing that contract is outside this fix. Each attempt remains bounded by the configured global
budget remaining and the configured per-model timeout; configuring both to large values intentionally
widens the overall budget.

Numeric helpers will be small, typed, and side-effect-free. Float parsing catches conversion errors,
uses `math.isfinite()`, and applies the setting-specific sign rule. Integer parsing uses
`int(value.strip(), 10)` to preserve the prior acceptance of whitespace, `+260`, and leading zeros;
it rejects zero, negative, decimal, exponent, hexadecimal, non-integer, and excessively long values
by returning the default. No logging occurs during import.

When `OLLAMA_URL` is absent, `compat.ollama_client.DEFAULT_URL` remains the preferred source when the
harness exposes it, then passes through safe normalization. Invalid explicit or harness-provided URLs
fall back to the canonical `http://127.0.0.1:11434`.

URL acceptance is exact: `scheme == "http"`, host in `localhost` / `127.0.0.1` / `::1`, path either
empty or `/`, no username/password/query/fragment/params, and port absent or within `1..65535`.
Port `0` is invalid. IPv6 is emitted as `[::1]`; a root slash may be normalized away as it is not part
of the base authority.

### Files

- `src/prompt_improve/shared/config.py`: safe import-time numeric parsing.
- `src/prompt_improve/shared/ollama_url.py`: total loopback URL normalization and IPv6 output.
- `tests/test_config.py`: direct helper/URL tables plus clean-process import, module, and shim tests.
- `README.md`: concise environment table documenting defaults, accepted values, fallback, and the
  cache-disable contract.

## System-Wide Impact

### Interaction graph

`prompt-improve.py` or the installed console script imports `prompt_improve.command`, which imports
feature modules, which import `shared.config`. Safe parsing allows import to complete; normal input
handling then reaches `_improve_and_emit()`, local/cloud routing, cache access, and the existing
fail-open guard.

### Error propagation

Malformed user configuration becomes a local default-selection decision instead of a `ValueError`
escaping module import. Operational pipeline errors remain governed by `command.main()` and the
existing Ollama/cloud exception contracts; this change must not broaden those catches.

### State lifecycle

No persistent state format changes. Cache schema and key semantics remain unchanged. A repaired TTL
may change whether a malformed environment uses cache, but only by restoring the documented default.

### API surface parity

The package import, `python -m prompt_improve.command`, installed `prompt-improve` script, and wired
shim all share `shared.config`; tests cover import, shim, and module execution. The installed console
script is not separately invoked from the source suite because it resolves the same declared
`prompt_improve.command:main` target and may not be installed in a clean checkout.

## Acceptance Criteria

- [x] Import succeeds with text, blank, non-finite, zero, and negative timeout values and chooses
      defaults according to the table.
- [x] Cache TTL retains the documented finite `<= 0` disable behavior; non-finite input defaults.
- [x] Rewrite threshold accepts only positive decimal integers and otherwise defaults.
- [x] URL normalization never raises for malformed string inputs.
- [x] Remote/HTTPS/malformed/extraneous URL inputs—including invalid IPv6, credentials, path, query,
      fragment, port zero, non-numeric port, and out-of-range port—fall back to the loopback default.
- [x] Valid `localhost`, IPv4 loopback, and bracketed IPv6 loopback URLs remain usable.
- [x] A shim subprocess with invalid configuration exits zero and emits parseable hook JSON.
- [x] A clean-process import and `python -m prompt_improve.command` execution succeed with invalid
      configuration; the module path preserves direct-CLI output.
- [x] Disabled cache TTL does not create, prune, or otherwise mutate cache files through `save_cached`.
- [x] Existing local-model budget, cache, model fallback, target-profile, and rewrite-size invariants
      remain green.
- [x] `pytest`, Ruff format/lint, type checking, and the applicable `codescan` sensors pass.

## Risks and Mitigations

- **Compatibility:** Preserve finite negative cache TTL as cache-disabled because current code treats
  all `<= 0` values that way.
- **Import-state tests:** Use subprocesses for environment-dependent config cases so module caching
  cannot hide failures or contaminate the main pytest process.
- **Network isolation:** Use the trivial prompt `ok` for shim/module smokes so successful import
  immediately takes the deterministic passthrough path without Ollama or cloud access.
- **URL behavior drift:** Table-test the current safe IPv4/localhost cases alongside malformed and
  IPv6 cases.
- **Overbroad fail-open:** Keep validation in the configuration boundary; do not add new blanket
  exception handling to feature code.

## Validation Plan

1. Focused table tests for numeric helpers and URL normalization, including `nan`, infinities,
   sign/zero rules, malformed authorities, and valid IPv6.
2. Clean-process config import that serializes constants, module execution, and shim JSON smoke with
   invalid env values. The shim assertion also verifies stderr does not contain `shim import failed`.
3. Full `python3 -m pytest tests/ -q`.
4. `python3 -m ruff check .` and `python3 -m ruff format --check .`.
5. Type check through `codescan type` or the project mypy gate.
6. `codescan all -p . --summary-only --json --fail-on never`.
7. Review `git diff --check`, scoped diff, and user-owned dirty memory change preservation.

## Alternatives Considered

- Catch import failures only in the shim: rejected because the console/module entry paths still fail
  and the shim emits no normal hook JSON.
- Move all configuration reads to call time: broader semantic change and unnecessary for the defect.
- Clamp every value to an arbitrary maximum: rejected to avoid silently overriding intentional local
  tuning without evidence.

## Sources and References

- `src/prompt_improve/shared/config.py`
- `src/prompt_improve/shared/ollama_url.py`
- `src/prompt_improve/command.py`
- `prompt-improve.py`
- `.memory-bank/systemPatterns.md` — fail-open hook and 24-second shared-budget invariants.
- Local SpecFlow and repository analysis performed 2026-07-12; no external research was needed.
