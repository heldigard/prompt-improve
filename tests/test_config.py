"""Configuration parsing and loopback URL boundary tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from prompt_improve.shared.config import (
    _finite_float,
    _positive_decimal_int,
    _positive_finite_float,
)
from prompt_improve.shared.ollama_url import DEFAULT_OLLAMA_URL, normalize_ollama_url

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CONFIG_ENV_VARS = (
    "OLLAMA_URL",
    "OLLAMA_IMPROVE_TIMEOUT",
    "OLLAMA_IMPROVE_TOTAL_TIMEOUT",
    "OLLAMA_IMPROVE_CACHE_TTL",
    "OLLAMA_IMPROVE_REWRITE_THRESHOLD",
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 45.0),
        ("", 45.0),
        ("garbage", 45.0),
        ("nan", 45.0),
        ("inf", 45.0),
        ("-inf", 45.0),
        ("0", 45.0),
        ("-1", 45.0),
        (" 0.25 ", 0.25),
    ],
)
def test_positive_finite_float(value: str | None, expected: float) -> None:
    assert _positive_finite_float(value, 45.0) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 300.0),
        ("", 300.0),
        ("garbage", 300.0),
        ("nan", 300.0),
        ("inf", 300.0),
        ("-inf", 300.0),
        ("0", 0.0),
        ("-1.5", -1.5),
        (" 12.5 ", 12.5),
    ],
)
def test_finite_float(value: str | None, expected: float) -> None:
    assert _finite_float(value, 300.0) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 260),
        ("", 260),
        ("2.4", 260),
        ("2e2", 260),
        ("0x104", 260),
        ("0", 260),
        ("-1", 260),
        ("+260", 260),
        ("0260", 260),
        (" 42 ", 42),
        ("9" * 5000, 260),
    ],
)
def test_positive_decimal_int(value: str | None, expected: int) -> None:
    assert _positive_decimal_int(value, 260) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, DEFAULT_OLLAMA_URL),
        ("", DEFAULT_OLLAMA_URL),
        (" http://localhost:11434/ ", "http://localhost:11434"),
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434"),
        ("http://127.0.0.2:11434", "http://127.0.0.2:11434"),
        ("http://[::1]:11434", "http://[::1]:11434"),
        ("http://[::1]", "http://[::1]"),
        ("https://localhost:11434", DEFAULT_OLLAMA_URL),
        ("http://example.com:11434", DEFAULT_OLLAMA_URL),
        ("http://192.0.2.1:11434", DEFAULT_OLLAMA_URL),
        ("http://localhost:0", DEFAULT_OLLAMA_URL),
        ("http://localhost:notaport", DEFAULT_OLLAMA_URL),
        ("http://localhost:65536", DEFAULT_OLLAMA_URL),
        ("http://[::1", DEFAULT_OLLAMA_URL),
        ("http://user@localhost:11434", DEFAULT_OLLAMA_URL),
        ("http://:secret@localhost:11434", DEFAULT_OLLAMA_URL),
        ("http://localhost:11434/api", DEFAULT_OLLAMA_URL),
        ("http://localhost:11434?x=1", DEFAULT_OLLAMA_URL),
        ("http://localhost:11434#fragment", DEFAULT_OLLAMA_URL),
    ],
)
def test_normalize_ollama_url_is_total_and_loopback_only(value: str | None, expected: str) -> None:
    assert normalize_ollama_url(value) == expected


def _clean_subprocess_env(**overrides: str) -> dict[str, str]:
    env = os.environ.copy()
    for name in CONFIG_ENV_VARS:
        env.pop(name, None)
    env.update(overrides)
    env["PYTHONPATH"] = str(SRC)
    return env


def test_invalid_environment_imports_with_defaults() -> None:
    code = """
import json
from prompt_improve.shared import config
print(json.dumps({
    "url": config.OLLAMA_URL,
    "timeout": config.OLLAMA_TIMEOUT,
    "total": config.OLLAMA_TOTAL_TIMEOUT,
    "ttl": config.CACHE_TTL_SECONDS,
    "threshold": config.REWRITE_THRESHOLD,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=_clean_subprocess_env(
            OLLAMA_URL="http://localhost:notaport",
            OLLAMA_IMPROVE_TIMEOUT="garbage",
            OLLAMA_IMPROVE_TOTAL_TIMEOUT="nan",
            OLLAMA_IMPROVE_CACHE_TTL="inf",
            OLLAMA_IMPROVE_REWRITE_THRESHOLD="2.4",
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "url": DEFAULT_OLLAMA_URL,
        "timeout": 45.0,
        "total": 20.0,
        "ttl": 300.0,
        "threshold": 260,
    }


def test_valid_environment_values_are_preserved() -> None:
    code = """
import json
from prompt_improve.shared import config
print(json.dumps({
    "url": config.OLLAMA_URL,
    "timeout": config.OLLAMA_TIMEOUT,
    "total": config.OLLAMA_TOTAL_TIMEOUT,
    "ttl": config.CACHE_TTL_SECONDS,
    "threshold": config.REWRITE_THRESHOLD,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=_clean_subprocess_env(
            OLLAMA_URL="http://[::1]:11434",
            OLLAMA_IMPROVE_TIMEOUT="0.25",
            OLLAMA_IMPROVE_TOTAL_TIMEOUT="1.5",
            OLLAMA_IMPROVE_CACHE_TTL="-1",
            OLLAMA_IMPROVE_REWRITE_THRESHOLD="+0260",
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "url": "http://[::1]:11434",
        "timeout": 0.25,
        "total": 1.5,
        "ttl": -1.0,
        "threshold": 260,
    }


def test_shim_emits_hook_json_with_invalid_environment() -> None:
    env = _clean_subprocess_env(
        PROMPT_IMPROVE_HOME=str(ROOT),
        OLLAMA_URL="http://[::1",
        OLLAMA_IMPROVE_TIMEOUT="garbage",
        OLLAMA_IMPROVE_TOTAL_TIMEOUT="nan",
        OLLAMA_IMPROVE_CACHE_TTL="inf",
        OLLAMA_IMPROVE_REWRITE_THRESHOLD="2.4",
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "prompt-improve.py")],
        cwd=ROOT,
        env=env,
        input=json.dumps({"prompt": "ok"}),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"continue": True}
    assert "shim import failed" not in result.stderr


def test_module_entrypoint_preserves_direct_cli_with_invalid_environment() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prompt_improve.command", "ok"],
        cwd=ROOT,
        env=_clean_subprocess_env(
            OLLAMA_URL="http://localhost:65536",
            OLLAMA_IMPROVE_TIMEOUT="garbage",
            OLLAMA_IMPROVE_TOTAL_TIMEOUT="nan",
            OLLAMA_IMPROVE_CACHE_TTL="inf",
            OLLAMA_IMPROVE_REWRITE_THRESHOLD="2.4",
        ),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "ok\n"
