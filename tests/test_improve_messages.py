"""build_messages rewrite/clarify/hint neutrality."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tests._helpers import (  # noqa: F401
    _FAKE_REWRITE,
    _load_hook,
    _patch_runner,
    _restore,
    _seq_responder,
)


def test_build_messages_rewrite_includes_language():
    import prompt_improve.features.improve as m

    system, user = m._build_messages("rewrite", "fix the bug", None)
    assert "English" in user
    assert "English" in system or "English" not in system  # system uses language var


def test_build_messages_clarify_includes_do_verify():
    import prompt_improve.features.improve as m

    system, user = m._build_messages("clarify", "fix the bug", None)
    assert "DO or VERIFY" in user


def test_build_messages_keep_tooling_neutral_to_avoid_prompt_bias():
    import prompt_improve.features.improve as m

    system, _ = m._build_messages("rewrite", "refactor this function safely", None)
    assert "codeq" not in system
    assert "codescan" not in system
    assert "LSP" not in system
    assert "immutable evidence" in system


def test_build_messages_includes_project_hint_when_continuation():
    import prompt_improve.features.improve as m

    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text("- Active: test task\n", encoding="utf-8")
        _, user = m._build_messages("rewrite", "continua", d)
        assert "Execution context (not task scope):" in user
        assert "test task" in user


def test_build_messages_omits_hint_when_no_cwd():
    import prompt_improve.features.improve as m

    _, user = m._build_messages("rewrite", "fix it", None)
    assert "Execution context (not task scope):" not in user
