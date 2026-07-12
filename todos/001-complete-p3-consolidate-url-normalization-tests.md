---
status: complete
priority: p3
issue_id: "001"
tags: [code-review, quality, tests]
dependencies: []
---

# Consolidate URL normalization tests

## Problem Statement

The new dedicated configuration test module covers all existing URL normalization cases plus the
new malformed-input and IPv6 boundaries. The older four-case test in `tests/test_improve.py` is now
duplicate coverage in the wrong feature slice.

## Findings

- `tests/test_improve.py::test_ollama_url_is_loopback_only` covers IPv4, localhost, HTTPS rejection,
  and remote-host rejection.
- `tests/test_config.py::test_normalize_ollama_url_is_total_and_loopback_only` covers those cases and
  the complete new boundary table.
- Keeping both creates two maintenance locations for the same transport/configuration contract.

## Proposed Solutions

### Option 1: Remove the superseded test

**Approach:** Delete the four-case test from `tests/test_improve.py` and keep the dedicated table.

**Pros:** One source of truth; preserves all behavior coverage.

**Cons:** Small test-count reduction.

**Effort:** Under 5 minutes.

**Risk:** Low.

### Option 2: Keep both tests

**Approach:** Accept intentional duplication as a cross-feature smoke.

**Pros:** No edit required.

**Cons:** Duplicated assertions and misleading test ownership.

**Effort:** None.

**Risk:** Low.

## Recommended Action

Remove the superseded test and run focused pytest validation.

## Technical Details

**Affected files:**

- `tests/test_improve.py`
- `tests/test_config.py`

No production code or persistent state is affected.

## Acceptance Criteria

- [x] The superseded URL test is removed from `tests/test_improve.py`.
- [x] Every removed assertion remains represented in `tests/test_config.py`.
- [x] Focused pytest suites pass.

## Work Log

### 2026-07-12 - Review discovery

**By:** Codex

**Actions:**

- Compared both test locations after the configuration hardening implementation.
- Confirmed complete assertion overlap.

**Learnings:**

- URL boundary behavior belongs with configuration tests, not LLM improvement routing tests.

### 2026-07-12 - Resolution

**By:** Codex

**Actions:**

- Removed `test_ollama_url_is_loopback_only` from `tests/test_improve.py`.
- Retained the dedicated parameterized configuration table as the single source of truth for
  loopback URL normalization, including IPv4, localhost, HTTPS rejection, remote-host rejection,
  malformed inputs, and IPv6 boundaries.
- Ran the focused configuration and improvement test modules successfully.

**Validation:**

- `pytest -q tests/test_config.py tests/test_improve.py`
- `ruff check tests/test_config.py tests/test_improve.py`
