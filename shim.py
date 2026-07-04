#!/usr/bin/env python3
"""Prompt-improve hook shim — delegates to the ``prompt_improve`` package (~/prompt-improve/).

The package is ``pip install -e``'d, so ``import prompt_improve`` resolves from any
CWD. This shim preserves the wired path ``~/.claude/hooks/improve-prompt.py`` so
``~/.claude/settings.json`` keeps resolving untouched.

Source of truth: ``~/prompt-improve/src/prompt_improve/``. History/changelog there.
If the package ever fails to import, fail OPEN (never block prompt submission).
"""
import sys

try:
    from prompt_improve.command import main
except Exception as exc:
    sys.stderr.write(f"[prompt-improve] shim import failed; falling back to no-op: {exc}\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
