"""Target CLI/model detection.

The "how" axis of target-awareness: given a hook payload + environment, infer
which CLI/model will receive the improved prompt and classify it into a family.

This module is imperative parsing/matching logic — it changes when detection
inputs or protocols change (new env var, new payload shape, new CLI). It knows
nothing about HOW to phrase prompts for each family; that lives in `shape.py`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TargetProfile:
    """The agent/model that will receive the improved prompt.

    `family` is the dispatch key into the prompt-shape registry (`shape.py`).
    `style` is an informative human-readable label (also folded into cache_key);
    it is NOT a dispatch key. `version` is best-effort extracted from the model
    string, used for cache partitioning.
    """

    cli: str
    model: str
    family: str
    version: str
    style: str

    @property
    def cache_key(self) -> str:
        return _slug(":".join((self.cli, self.family, self.version, self.style)))


GENERIC_TARGET = TargetProfile(
    cli="generic",
    model="unknown",
    family="generic",
    version="unknown",
    style="plain-markdown",
)


def target_profile_from_request(data: dict | None = None) -> TargetProfile:
    """Infer target CLI/model from hook payload and environment.

    Explicit env overrides are first-class because shell wrappers know more than
    hook payloads in proxied Claude Code and Codex profile launches.
    """
    data = data or {}
    cli = _first_text(
        os.environ.get("PROMPT_IMPROVE_TARGET_CLI"),
        os.environ.get("CODEX_TARGET_CLI"),
        os.environ.get("CLAUDE_TARGET_CLI"),
        os.environ.get("CLI_ORCHESTRATION_CALLER"),
        data.get("cli"),
        data.get("client"),
        data.get("tool"),
        data.get("app"),
    )
    if not cli:
        cli = _cli_from_payload(data)
    model = _first_text(
        os.environ.get("PROMPT_IMPROVE_TARGET_MODEL"),
        _model_from_payload(data),
        _model_from_env(),
        os.environ.get("ANTHROPIC_MODEL"),
        _model_from_agent_identity(os.environ.get("CLAUDE_AGENT_IDENTITY")),
    )

    if not cli:
        cli = _cli_from_env_or_model(model)
    if not model and cli == "codex":
        model = _codex_default_model()

    shape_by = os.environ.get("PROMPT_IMPROVE_SHAPE_BY", "model").strip().lower()
    # When shaping by CLI, the prompt follows the CLI's conventions (e.g. Claude
    # XML tags) even when a proxy routes to a different model family underneath.
    if shape_by == "cli" and cli:
        return profile_for_cli(cli, model or "unknown")
    return profile_for_model(model or "unknown", cli or "generic")


# Canonical CLI → (family, style) mapping. Single source of truth shared by
# profile_for_model's CLI fallback branch and profile_for_cli (the
# PROMPT_IMPROVE_SHAPE_BY=cli path), so both agree on which family/style a CLI
# maps to. 'codex' is included for profile_for_cli; profile_for_model returns
# earlier on the openai/codex branch before reaching this dict.
_CLI_FAMILY_STYLE: dict[str, tuple[str, str]] = {
    "claude": ("claude", "xml-tags"),
    "codex": ("openai-gpt", "codex-markdown"),
    "agy": ("gemini", "component-blocks"),
    "antigravity": ("gemini", "component-blocks"),
    "gemini": ("gemini", "component-blocks"),
    "qwen": ("qwen", "literal-markdown"),
    "qwenc": ("qwen", "literal-markdown"),
    "dseek": ("deepseek", "explicit-steps"),
    "deepseek": ("deepseek", "explicit-steps"),
    "mini": ("minimax", "agentic-markdown"),
    "minimax": ("minimax", "agentic-markdown"),
    "codex-minimax": ("minimax", "agentic-markdown"),
    "kimi": ("kimi", "agentic-markdown"),
    "kimic": ("kimi", "agentic-markdown"),
    "mimo": ("mimo", "explicit-steps"),
    "zai": ("glm", "explicit-steps"),
    "glm": ("glm", "explicit-steps"),
}


def profile_for_model(model: str, cli: str | None = None) -> TargetProfile:
    """Classify a model string into a family + style label.

    The family is the dispatch key consumed by `shape.target_guidance`. The
    style is a descriptive label only.
    """
    clean_model = model.strip() or "unknown"
    lower = clean_model.lower()
    clean_cli = (cli or _cli_from_env_or_model(clean_model) or "generic").lower()

    if _looks_like_claude(lower):
        return TargetProfile(
            clean_cli, clean_model, "claude", _version(lower), _claude_style(lower)
        )
    if _looks_like_gemini(lower):
        return TargetProfile(
            clean_cli, clean_model, "gemini", _version(lower), _gemini_style(lower)
        )
    if _looks_like_qwen(lower):
        return TargetProfile(clean_cli, clean_model, "qwen", _version(lower), _qwen_style(lower))
    if _looks_like_deepseek(lower):
        return TargetProfile(
            clean_cli, clean_model, "deepseek", _version(lower), _deepseek_style(lower)
        )
    if _looks_like_minimax(lower):
        return TargetProfile(
            clean_cli, clean_model, "minimax", _version(lower), _minimax_style(lower)
        )
    if _looks_like_kimi(lower):
        return TargetProfile(clean_cli, clean_model, "kimi", _version(lower), _kimi_style(lower))
    if _looks_like_mimo(lower):
        return TargetProfile(clean_cli, clean_model, "mimo", _version(lower), "explicit-steps")
    if _looks_like_glm(lower):
        return TargetProfile(clean_cli, clean_model, "glm", _version(lower), "explicit-steps")
    if _looks_like_gemma(lower):
        return TargetProfile(clean_cli, clean_model, "gemma", _version(lower), "compact-markdown")
    if _looks_like_openai(lower) or clean_cli == "codex":
        return TargetProfile(
            clean_cli, clean_model, "openai-gpt", _version(lower), _openai_style(lower)
        )
    cli_style = _CLI_FAMILY_STYLE.get(clean_cli)
    if cli_style is not None:
        family, style = cli_style
        return TargetProfile(clean_cli, clean_model, family, _version(lower), style)
    return TargetProfile(clean_cli, clean_model, "generic", _version(lower), "plain-markdown")


def profile_for_cli(cli: str, model: str = "unknown") -> TargetProfile:
    """Build a profile whose family/style follow the CLI, not the underlying model.

    Used when ``PROMPT_IMPROVE_SHAPE_BY=cli``: under a proxy (e.g. Claude Code on
    a GLM backend) a user may want the prompt shaped for the CLI's conventions
    (Claude XML tags) rather than the model the proxy routes to. The real model
    is still carried for cache partitioning and version notes.
    """
    clean_cli = (cli or "generic").lower()
    clean_model = (model or "unknown").strip()
    family, style = _CLI_FAMILY_STYLE.get(clean_cli, ("generic", "plain-markdown"))
    return TargetProfile(clean_cli, clean_model, family, _version(clean_model.lower()), style)


# ---- payload / env parsing -------------------------------------------------


def _model_from_payload(data: dict) -> str | None:
    model = data.get("model")
    if isinstance(model, str):
        return model
    if isinstance(model, dict):
        return _first_text(
            model.get("id"),
            model.get("name"),
            model.get("display_name"),
            model.get("slug"),
        )
    return _first_text(
        data.get("model_id"),
        data.get("model_name"),
        data.get("active_model"),
        data.get("selected_model"),
        data.get("modelName"),
    )


def _cli_from_payload(data: dict) -> str | None:
    """Infer the harness from fields that are specific to its hook contract."""
    event = _first_text(data.get("hook_event_name"), data.get("hookEventName"))
    if event == "UserPromptSubmit" and isinstance(data.get("transcript_path"), str):
        return "claude"
    return None


def _model_from_env() -> str | None:
    """Best-effort active-model lookup across CLI wrappers.

    Values are model IDs, not secrets. API-key env vars are intentionally not read.
    """
    return _first_text(
        os.environ.get("CODEX_MODEL"),
        os.environ.get("OPENAI_MODEL"),
        os.environ.get("OPENAI_API_MODEL"),
        os.environ.get("CLAUDE_MODEL"),
        os.environ.get("ANTHROPIC_MODEL"),
        os.environ.get("GEMINI_MODEL"),
        os.environ.get("GOOGLE_MODEL"),
        os.environ.get("AGY_MODEL"),
        os.environ.get("DEEPSEEK_MODEL"),
        os.environ.get("QWEN_MODEL"),
        os.environ.get("KIMI_MODEL"),
        os.environ.get("MINIMAX_MODEL"),
        os.environ.get("ZAI_MODEL"),
        os.environ.get("GLM_MODEL"),
        os.environ.get("MODEL_NAME"),
        os.environ.get("MODEL_ID"),
        os.environ.get("MODEL"),
    )


def _model_from_agent_identity(identity: str | None) -> str | None:
    if not identity:
        return None
    parts = identity.split(":")
    return parts[1] if len(parts) >= 2 and parts[1] else None


def _cli_from_env_or_model(model: str | None) -> str | None:
    identity = os.environ.get("CLAUDE_AGENT_IDENTITY")
    if identity and ":" in identity:
        cli = identity.split(":", 1)[0].strip()
        if cli:
            return "antigravity" if cli == "gemini" else cli
    # Prefer explicit harness markers only. A blanket CLAUDE_CODE_* / CODEX_*
    # prefix match is too aggressive: nested shells under Claude Code export
    # flags like CLAUDE_CODE_DISABLE_TERMINAL_TITLE that would mis-label
    # Codex/Gemini/Grok sessions as Claude (breaks permission_mode-only
    # payloads and non-Claude hooks that inherit the parent env).
    if os.environ.get("CODEX_WORKER") or os.environ.get("CODEX_SANDBOX"):
        return "codex"
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude"
    if os.environ.get("ANTHROPIC_MODEL") or os.environ.get("ANTHROPIC_BASE_URL"):
        return "claude"
    if os.environ.get("AGY_SETTINGS"):
        return "antigravity"
    lower = (model or "").lower()
    if _looks_like_claude(lower):
        return "claude"
    if _looks_like_gemini(lower):
        return "antigravity"
    if _looks_like_openai(lower):
        return "codex"
    if _looks_like_minimax(lower):
        return "mini"
    if _looks_like_kimi(lower):
        return "kimi"
    if _looks_like_deepseek(lower):
        return "dseek"
    if _looks_like_qwen(lower):
        return "qwen"
    if _looks_like_glm(lower):
        return "zai"
    return None


def _codex_default_model() -> str | None:
    path = os.path.expanduser("~/.codex/config.toml")
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                match = re.match(r'\s*model\s*=\s*["\']([^"\']+)["\']', line)
                if match:
                    return match.group(1)
    except OSError:
        return None
    return None


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


# ---- family matchers -------------------------------------------------------


def _looks_like_claude(text: str) -> bool:
    return any(token in text for token in ("claude", "sonnet", "opus", "haiku", "fable", "mythos"))


def _looks_like_openai(text: str) -> bool:
    return bool(re.search(r"\b(gpt|o[1345]|codex)\b", text))


def _looks_like_gemini(text: str) -> bool:
    return "gemini" in text or "antigravity" in text


def _looks_like_qwen(text: str) -> bool:
    return "qwen" in text


def _looks_like_deepseek(text: str) -> bool:
    return "deepseek" in text


def _looks_like_minimax(text: str) -> bool:
    return "minimax" in text or "mini-max" in text or bool(re.search(r"\bminimax-m?\d", text))


def _looks_like_kimi(text: str) -> bool:
    return "kimi" in text


def _looks_like_mimo(text: str) -> bool:
    return "mimo" in text


def _looks_like_glm(text: str) -> bool:
    return "glm" in text or "z.ai" in text or "zai" in text


def _looks_like_gemma(text: str) -> bool:
    return "gemma" in text


# ---- helpers ---------------------------------------------------------------


def _claude_style(text: str) -> str:
    if "opus" in text or "fable" in text or "mythos" in text:
        return "xml-tags-longctx"
    return "xml-tags"


def _openai_style(text: str) -> str:
    if "codex" in text:
        return "codex-outcome-first"
    if re.search(r"\bgpt-5(?:\.5|\b|-)", text):
        return "gpt5-outcome-first"
    return "codex-markdown"


def _gemini_style(text: str) -> str:
    if re.search(r"\bgemini[- ]?3", text):
        return "gemini3-concise-blocks"
    return "component-blocks"


def _qwen_style(text: str) -> str:
    if "coder" in text or "code" in text:
        return "qwen-coder-literal"
    if re.search(r"\bqwen3\b|\bqwen3[.-]", text):
        return "qwen3-literal"
    return "literal-markdown"


def _deepseek_style(text: str) -> str:
    # R1 / deepseek-reasoner is a PURE reasoning model (distinct prompting: no
    # system prompt, zero-shot, temp ~0.6) — must not be conflated with V3/V4
    # instruct models. Source: DeepSeek-R1 README (api-docs.deepseek.com).
    if "r1" in text or "reasoner" in text:
        return "deepseek-r1-reasoner"
    if "v4" in text:
        return "deepseek-v4-reasoning"
    return "explicit-steps"


def _minimax_style(text: str) -> str:
    if re.search(r"\bm3\b|m3", text):
        return "minimax-m3-longctx"
    return "agentic-markdown"


def _kimi_style(text: str) -> str:
    if "2.7" in text or "k2.7" in text:
        return "kimi-k2.7-code"
    return "agentic-markdown"


def _version(text: str) -> str:
    match = re.search(r"(\d+(?:\.\d+){0,2}(?:-[a-z0-9.]+)?)", text)
    return match.group(1) if match else "unknown"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", text.lower()).strip("-") or "generic"
