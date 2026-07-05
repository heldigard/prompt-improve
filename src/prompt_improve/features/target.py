"""Target CLI/model detection and prompt-shape guidance."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re


@dataclass(frozen=True)
class TargetProfile:
    """The agent/model that will receive the improved prompt."""

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
        data.get("cli"),
        data.get("client"),
        data.get("tool"),
    )
    model = _first_text(
        os.environ.get("PROMPT_IMPROVE_TARGET_MODEL"),
        _model_from_payload(data),
        os.environ.get("ANTHROPIC_MODEL"),
        _model_from_agent_identity(os.environ.get("CLAUDE_AGENT_IDENTITY")),
        os.environ.get("CODEX_MODEL"),
        os.environ.get("AGY_MODEL"),
    )

    if not cli:
        cli = _cli_from_env_or_model(model)
    if not model and cli == "codex":
        model = _codex_default_model()

    return profile_for_model(model or "unknown", cli or "generic")


def profile_for_model(model: str, cli: str | None = None) -> TargetProfile:
    """Classify a model string into a prompt formatting family."""
    clean_model = model.strip() or "unknown"
    lower = clean_model.lower()
    clean_cli = (cli or _cli_from_env_or_model(clean_model) or "generic").lower()

    if _looks_like_claude(lower):
        return TargetProfile(clean_cli, clean_model, "claude", _version(lower), "xml-tags")
    if _looks_like_openai(lower) or clean_cli == "codex":
        return TargetProfile(clean_cli, clean_model, "openai-gpt", _version(lower), "codex-markdown")
    if _looks_like_gemini(lower) or clean_cli in {"agy", "antigravity", "gemini"}:
        return TargetProfile(clean_cli, clean_model, "gemini", _version(lower), "component-blocks")
    if _looks_like_qwen(lower):
        return TargetProfile(clean_cli, clean_model, "qwen", _version(lower), "literal-markdown")
    if _looks_like_deepseek(lower):
        return TargetProfile(clean_cli, clean_model, "deepseek", _version(lower), "explicit-steps")
    if _looks_like_minimax(lower):
        return TargetProfile(clean_cli, clean_model, "minimax", _version(lower), "agentic-markdown")
    if _looks_like_glm(lower):
        return TargetProfile(clean_cli, clean_model, "glm", _version(lower), "explicit-steps")
    if _looks_like_gemma(lower):
        return TargetProfile(clean_cli, clean_model, "gemma", _version(lower), "compact-markdown")
    return TargetProfile(clean_cli, clean_model, "generic", _version(lower), "plain-markdown")


def target_guidance(target: TargetProfile, mode: str, language: str) -> str:
    """Prompt-shape instructions for the target model family."""
    if target.family == "claude":
        return _claude_guidance(mode, language)
    if target.family == "openai-gpt":
        return _openai_guidance(mode, language)
    if target.family == "gemini":
        return _gemini_guidance(mode, language)
    if target.family in {"qwen", "deepseek", "glm", "minimax"}:
        return _literal_guidance(mode)
    if target.family == "gemma":
        return _compact_guidance(mode)
    return _generic_guidance(mode)


def _claude_guidance(mode: str, language: str) -> str:
    labels = "Spanish labels" if language == "Spanish" else "English labels"
    if mode == "rewrite":
        return (
            "Target model profile: Claude family. Output the rewritten prompt with "
            "short XML-style sections using stable tags such as <task>, <context>, "
            "<constraints>, and <acceptance>. Keep human-visible text in the user's "
            f"language ({labels}). Put context before the final task when source "
            "material is present. Do not wrap the whole answer in markdown fences."
        )
    return (
        "Target model profile: Claude family. Use concise bullets and, where a "
        "bullet names separate material, prefer XML tag names like <context> or "
        "<acceptance> so Claude can parse instructions, context, and input cleanly."
    )


def _openai_guidance(mode: str, language: str) -> str:
    if mode == "rewrite":
        return (
            "Target model profile: OpenAI GPT/Codex. Output clean Markdown sections "
            "with explicit role/workflow guidance, concrete tool-use or verification "
            "steps when inferable, and backticks around file paths/functions/classes. "
            "Separate instructions from the user's original input; do not use XML."
        )
    return (
        "Target model profile: OpenAI GPT/Codex. Use 1-3 Markdown bullets that "
        "name concrete actions, verification, and any TODO/planning need. Use "
        "backticks for paths/functions/classes. Do not use XML."
    )


def _gemini_guidance(mode: str, language: str) -> str:
    if mode == "rewrite":
        return (
            "Target model profile: Gemini/Antigravity. Output clearly labeled "
            "component blocks: Objective, Instructions, Context, Constraints, and "
            "Output format, using only blocks that are inferable. Keep the user's "
            "source/context before the final request when present, and use simple "
            "delimiters instead of XML."
        )
    return (
        "Target model profile: Gemini/Antigravity. Use component-style bullets that "
        "separate objective, instruction, context, and output/verification format."
    )


def _literal_guidance(mode: str) -> str:
    if mode == "rewrite":
        return (
            "Target model profile: literal instruction follower. Use direct, "
            "numbered or plainly labeled Markdown. Avoid implicit intent, hidden "
            "assumptions, and broad discretionary language."
        )
    return (
        "Target model profile: literal instruction follower. Make each bullet a "
        "direct action or verification step with minimal ambiguity."
    )


def _compact_guidance(mode: str) -> str:
    if mode == "rewrite":
        return (
            "Target model profile: compact local model. Keep the output short, flat, "
            "and strongly labeled. Avoid nested structure and long explanations."
        )
    return "Target model profile: compact local model. Keep bullets short and concrete."


def _generic_guidance(mode: str) -> str:
    if mode == "rewrite":
        return "Target model profile: generic. Use clear, flat Markdown sections."
    return "Target model profile: generic. Use concise action bullets."


def _model_from_payload(data: dict) -> str | None:
    model = data.get("model")
    if isinstance(model, str):
        return model
    if isinstance(model, dict):
        return _first_text(model.get("id"), model.get("name"), model.get("display_name"))
    return _first_text(data.get("model_id"), data.get("model_name"))


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
    if os.environ.get("CODEX_WORKER") or any(k.startswith("CODEX_") for k in os.environ):
        return "codex"
    if os.environ.get("ANTHROPIC_MODEL") or os.environ.get("ANTHROPIC_BASE_URL"):
        return "claude"
    if os.environ.get("AGY_SETTINGS"):
        return "antigravity"
    lower = (model or "").lower()
    if _looks_like_openai(lower):
        return "codex"
    if _looks_like_gemini(lower):
        return "antigravity"
    if _looks_like_claude(lower):
        return "claude"
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
    return "minimax" in text or "mini" in text


def _looks_like_glm(text: str) -> bool:
    return "glm" in text or "z.ai" in text or "zai" in text


def _looks_like_gemma(text: str) -> bool:
    return "gemma" in text


def _version(text: str) -> str:
    match = re.search(r"(\d+(?:\.\d+){0,2}(?:-[a-z0-9.]+)?)", text)
    return match.group(1) if match else "unknown"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", text.lower()).strip("-") or "generic"
