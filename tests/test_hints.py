"""Tests for prompt_improve.features.hints: project_hint extraction from .memory-bank/currentTask.md and deterministic continuation_context."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from tests import compat as ip


def test_project_hint_empty_when_no_cwd():
    assert ip._project_hint(None) == ""
    assert ip._project_hint("") == ""


def test_project_hint_reads_currenttask():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "# Current Task\n\n- Refactor the billing service to use events\n",
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "currentTask=" in hint
        assert "Refactor the billing service" in hint


def test_project_hint_rejects_currenttask_symlink_outside_bank(tmp_path: Path):
    bank = tmp_path / "project" / ".memory-bank"
    bank.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("- Active: sensitive outside task\n", encoding="utf-8")
    (bank / "currentTask.md").symlink_to(outside)

    hint = ip._project_hint(str(bank.parent))

    assert "sensitive outside task" not in hint
    assert "currentTask=" not in hint


def test_project_hint_rejects_symlinked_memory_bank(tmp_path: Path):
    outside_bank = tmp_path / "outside-bank"
    outside_bank.mkdir()
    (outside_bank / "currentTask.md").write_text(
        "- Active: sensitive task in linked bank\n",
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()
    (project / ".memory-bank").symlink_to(outside_bank, target_is_directory=True)

    hint = ip._project_hint(str(project))

    assert "sensitive task" not in hint
    assert "currentTask=" not in hint


def test_project_hint_rejects_oversized_currenttask(tmp_path: Path):
    bank = tmp_path / ".memory-bank"
    bank.mkdir()
    (bank / "currentTask.md").write_text(
        "- Active: " + ("x" * 64_001),
        encoding="utf-8",
    )

    assert "currentTask=" not in ip._project_hint(str(tmp_path))


def test_project_hint_skips_historical_completed_task_lines():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "\n".join(
                [
                    "# Current Task",
                    "- Status (2026-06-15, history): old Spring Boot migration",
                    "- RTK token-optimization subsystem (2026-06-15, COMPLETE): shipped",
                    "- Active: fix memory-bank project isolation for Claude hooks",
                ]
            ),
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "Spring Boot" not in hint
        assert "COMPLETE" not in hint
        assert "memory-bank project isolation" in hint


def test_project_hint_skips_last_deploy_when_no_active_task():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "\n".join(
                [
                    "# Current Task",
                    "## Estado: Sin tarea Codex activa (2026-07-01)",
                    "Ultimo trabajo Codex cerrado: mejoras moviles de ordenes y cotizaciones.",
                    "- T0-T5 + cleanup cosmetico: todos completos.",
                    "Ultimo deploy Codex: quote-conversion password guard.",
                ]
            ),
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "quote-conversion" not in hint
        assert "password guard" not in hint
        assert "currentTask=" not in hint


def test_project_hint_skips_checked_items_in_completed_currenttask():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "\n".join(
                [
                    "# currentTask",
                    "## Spring Boot 4 Migration Assistance (Completed)",
                    "Coordinating with Claude to resolve old test failures.",
                    "- [x] Fix UserGatewayImpl session handling.",
                    "- [ ] DEBT - extract shared SessionFilterHelper.",
                ]
            ),
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "UserGatewayImpl" not in hint
        assert "Coordinating with Claude" not in hint
        assert "SessionFilterHelper" in hint


def test_prompt_project_hint_omits_currenttask_for_concrete_continuation():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: quote-conversion password guard\n",
            encoding="utf-8",
        )
        hint = ip._project_hint_for_prompt(
            "continua con las mejoras moviles de cotizaciones; faltan boton y texto",
            d,
        )
        assert hint == f"cwd={Path(d).name}"
        assert "quote-conversion" not in hint


def test_prompt_project_hint_omits_currenttask_for_short_object_continuation():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: quote-conversion password guard\n",
            encoding="utf-8",
        )
        hint = ip._project_hint_for_prompt("continua con cotizaciones", d)
        assert hint == f"cwd={Path(d).name}"
        assert "quote-conversion" not in hint


def test_prompt_project_hint_keeps_currenttask_for_bare_continue():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: fix memory-bank project isolation\n",
            encoding="utf-8",
        )
        hint = ip._project_hint_for_prompt("continua", d)
        assert "currentTask=Active: fix memory-bank project isolation" in hint


def test_prompt_project_hint_keeps_currenttask_for_polite_bare_continue():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: fix memory-bank project isolation\n",
            encoding="utf-8",
        )
        hint = ip._project_hint_for_prompt("continua por favor", d)
        assert "currentTask=Active: fix memory-bank project isolation" in hint


def test_continuation_context_is_deterministic_from_currenttask():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "- Active: extract shared SessionFilterHelper so the no-op-close proxy "
            "lives in one place instead of duplicated in GenericBasicGatewayImpl "
            "and DeliveryOrderQueryDelegate\n",
            encoding="utf-8",
        )
        context = ip._continuation_context("continua", d)
        assert context is not None
        assert "extract shared SessionFilterHelper" in context
        assert "DeliveryOrderQueryDelegate" in context
        assert "verifica archivos" in context


def test_continuation_context_empty_without_currenttask():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "## Estado: Sin tarea Codex activa\nUltimo deploy: quote-conversion\n",
            encoding="utf-8",
        )
        assert ip._continuation_context("continua", d) is None


def test_project_hint_prefers_recent_active_task_over_generic_scope():
    with tempfile.TemporaryDirectory() as d:
        mb = Path(d) / ".memory-bank"
        mb.mkdir()
        (mb / "currentTask.md").write_text(
            "\n".join(
                [
                    "# Current Task",
                    "- Maintain home-level cross-CLI config.",
                    "- **Status (2026-06-24):** completed memory subsystem hardening.",
                    "- **Active (2026-07-01):** improve second-opinion routing and memory freshness.",
                ]
            ),
            encoding="utf-8",
        )
        hint = ip._project_hint(d)
        assert "second-opinion routing" in hint
        assert "Maintain home-level" not in hint
        assert ":**" not in hint


def test_project_hint_filters_stale_active_task_lines():
    # runner llama sin fixtures pytest — set/restore env manual
    prev = os.environ.get("MEMORY_INJECTION_ACTIVE_WINDOW_HOURS")
    os.environ["MEMORY_INJECTION_ACTIVE_WINDOW_HOURS"] = "12"
    try:
        with tempfile.TemporaryDirectory() as d:
            mb = Path(d) / ".memory-bank"
            mb.mkdir()
            (mb / "currentTask.md").write_text(
                "\n".join(
                    [
                        "# Current Task",
                        "- 2020-01-01T00:00:00Z | status:active | stale prompt-improver task",
                        "- 2026-01-01T00:00:00Z | status:live | stable prompt-improver task",
                    ]
                ),
                encoding="utf-8",
            )
            hint = ip._project_hint(d)
            assert "stale prompt-improver task" not in hint
            assert "stable prompt-improver task" in hint
    finally:
        if prev is None:
            os.environ.pop("MEMORY_INJECTION_ACTIVE_WINDOW_HOURS", None)
        else:
            os.environ["MEMORY_INJECTION_ACTIVE_WINDOW_HOURS"] = prev


def test_project_hint_without_memory_bank_returns_cwd_only():
    with tempfile.TemporaryDirectory() as d:
        hint = ip._project_hint(d)
        assert hint.startswith("cwd=")
        assert "currentTask=" not in hint
