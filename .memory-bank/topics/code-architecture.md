# Code Architecture

> Per-project symbol map + dependency graph + convention notes. Loaded on demand.
> Complements the `code-intelligence` skill (LSP-based semantic code analysis).
> Budget: ≤300 lines.

## Module Map

Map of major directories and their purpose in this project.

- `src/` — main source
- `tests/` — test suite
- `docs/` — documentation

## Symbol Index (key symbols only)

For full symbol search, use the `code-intelligence` skill (LSP-based). This index is for symbols the agent should know immediately without re-searching.

| Symbol | Location | Purpose |
|--------|----------|---------|
| _example class_ | `src/models/example.py:15` | _what it does_ |
| _main entry_ | `src/main.py:1` | _entry point_ |

## Dependency Graph

For hot paths or architectural overview. Not exhaustive.

```
api/*     →  services/*  →  repositories/*  →  models/*
cli/*     →  services/*
workers/* →  services/*  (async)
```

## Convention Notes

Project-specific patterns, gotchas, naming conventions that an agent should respect.

- Type hints required on public functions
- Async/await for I/O; sync for pure functions
- Tests in `tests/` mirror source structure
- Logging via `structlog` (not `print` or stdlib `logging`)
- Errors: raise domain exceptions, never bare `Exception`
