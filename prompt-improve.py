#!/usr/bin/env python3
"""Prompt-improve hook shim — delegates to the ``prompt_improve`` package (~/prompt-improve/).

The shim bootstraps the source tree directly, so it still works when a worker
uses an isolated ``HOME`` and Python cannot see user-site editable installs.
This preserves the wired path ``~/.claude/hooks/prompt-improve.py`` so
``~/.claude/settings.json`` keeps resolving untouched.

Source of truth: ``~/prompt-improve/src/prompt_improve/``. History/changelog there.
If the package ever fails to import, fail OPEN (never block prompt submission).
"""

import os
import sys
from pathlib import Path


def _bootstrap_source() -> None:
    candidates = []
    if home := os.environ.get("PROMPT_IMPROVE_HOME"):
        candidates.append(Path(home))
    here = Path(__file__).resolve()
    candidates.extend([here.parent, here.parent.parent])
    try:
        candidates.append(here.parents[2] / "prompt-improve")
    except IndexError:
        pass
    candidates.append(Path.home() / "prompt-improve")

    for project in candidates:
        src = project / "src"
        if src.exists():
            sys.path.insert(0, str(src))
            return


_bootstrap_source()

try:
    from prompt_improve.command import main
except Exception as exc:
    sys.stderr.write(f"[prompt-improve] shim import failed; falling back to no-op: {exc}\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
