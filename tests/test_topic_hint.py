"""Topic-hint synergy: prompt-improve reads agent-memory's ``topics/_index.md``.

Deterministic keyword-overlap bridge — no LLM, no embeddings. Fail-open when
the index is absent, empty, or has no real overlap with the prompt.
"""

from __future__ import annotations

from pathlib import Path

from prompt_improve.shared.paths import (
    _existing_path_correction,
    _topic_hint,
    project_hint_for_prompt,
)


def _write_index(bank: Path, body: str) -> None:
    topics = bank / "topics"
    topics.mkdir(parents=True, exist_ok=True)
    (topics / "_index.md").write_text(body, encoding="utf-8")


def test_topic_hint_empty_when_no_index(tmp_path: Path) -> None:
    bank = tmp_path / ".memory-bank"
    bank.mkdir()
    assert _topic_hint("auth flow", tmp_path) == ""


def test_topic_hint_empty_when_only_tbd(tmp_path: Path) -> None:
    bank = tmp_path / ".memory-bank"
    bank.mkdir()
    _write_index(bank, "# Topic Index\n## Topics\n- TBD\n")
    assert _topic_hint("auth flow", tmp_path) == ""


def test_topic_hint_matches_on_keyword_overlap(tmp_path: Path) -> None:
    bank = tmp_path / ".memory-bank"
    bank.mkdir()
    _write_index(
        bank,
        "# Topic Index\n## Topics\n"
        "- [Auth Flow](auth-flow.md) — token/session lifecycle\n"
        "- [Deploy Runbook](deploy.md) — zip-push steps\n",
    )
    out = _topic_hint("explain the auth token expiry refresh", tmp_path)
    assert out == "topic=auth-flow (Auth Flow)"


def test_topic_hint_empty_when_only_stopword_overlap(tmp_path: Path) -> None:
    bank = tmp_path / ".memory-bank"
    bank.mkdir()
    _write_index(
        bank,
        "## Topics\n- [Auth Flow](auth-flow.md) — token lifecycle\n",
    )
    # every token here is a stopword
    assert _topic_hint("the a an of for to in on", tmp_path) == ""


def test_project_hint_appends_topic_on_overlap(tmp_path: Path) -> None:
    bank = tmp_path / ".memory-bank"
    bank.mkdir()
    _write_index(
        bank,
        "## Topics\n- [Quote Engine](quote-engine.md) — pricing workflow\n",
    )
    hint = project_hint_for_prompt("how does the pricing workflow quote", str(tmp_path))
    assert "cwd=" in hint
    assert "topic=quote-engine" in hint


def test_project_hint_omits_operational_session_topics(tmp_path: Path) -> None:
    bank = tmp_path / ".memory-bank"
    bank.mkdir()
    _write_index(
        bank,
        "## Topics\n"
        "- [Foreign Sessions](foreign-sessions.md) — cross-CLI registry\n"
        "- [Agent Sessions](agent-sessions.md) — old worker activity\n",
    )
    hint = project_hint_for_prompt("how do foreign sessions register", str(tmp_path))
    assert hint == f"cwd={tmp_path.name}"


def test_project_hint_omits_topic_without_overlap(tmp_path: Path) -> None:
    bank = tmp_path / ".memory-bank"
    bank.mkdir()
    _write_index(bank, "## Topics\n- [Auth Flow](auth-flow.md) — token lifecycle\n")
    hint = project_hint_for_prompt("fix the typo in README", str(tmp_path))
    assert hint == f"cwd={tmp_path.name}"


def test_existing_path_correction_only_returns_verified_sibling(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "ollama-bench").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    hint = _existing_path_correction("revisa ~/ollama-bech/")
    assert hint == ("verified path correction candidate: ~/ollama-bech/ -> ~/ollama-bench/")


def test_existing_path_correction_does_not_guess_without_match(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "unrelated").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert _existing_path_correction("revisa ~/ollama-bech/") == ""
