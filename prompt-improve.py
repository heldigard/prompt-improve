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
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    if home := os.environ.get("PROMPT_IMPROVE_HOME"):
        candidates.append(Path(home).expanduser())
    candidates.extend((here.parent, here.parent.parent, Path.home() / "prompt-improve"))
    candidates.extend(parent / "prompt-improve" for parent in here.parents)

    seen: set[Path] = set()
    for project in candidates:
        if project in seen:
            continue
        seen.add(project)
        source = project / "src"
        if source.is_dir():
            source_text = str(source)
            if source_text not in sys.path:
                sys.path.insert(0, source_text)
            return


_bootstrap_source()

try:
    from prompt_improve.command import main
except Exception as exc:
    sys.stderr.write(f"[prompt-improve] shim import failed; falling back to no-op: {exc}\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
