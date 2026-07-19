# Active Context
> Updated: 2026-07-19

## Handoff
- **v17.2.0**: Grok target family shipped; improve tests split into per-concern modules.
- CLI: `prompt-improve detect|classify|improve|target`; hook entry raises `SystemExit` for subcommands.
- Improve chain: cryptidbleh → TeichAI → Negentropy-9B → SetneufPT.
- Pipeline: `CLI_ORCHESTRATION_CALLER=grok` is a controller (swarm-auto-delegate allowed).

## Verify
```bash
uv run pytest && uv run ruff check .
prompt-improve --help
prompt-improve detect --prompt "fix foo.py"
```
