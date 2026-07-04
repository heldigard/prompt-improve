# vs-soft-allow: nesting_depth — for/try/if is the natural shape of retry loops over model APIs; params are config for a generic model-runner
"""LLM calls: Ollama clarify/rewrite, cloud cascade, intelligent router."""

from __future__ import annotations

from collections.abc import Callable

from prompt_improve.features.classify import needs_cloud_intelligence
from prompt_improve.features.clean import clean_response, clean_rewrite
from prompt_improve.features.detect import detect_language
from prompt_improve.features.rules import SYSTEM_PROMPT, build_rewrite_system_prompt
from prompt_improve.shared import compat
from prompt_improve.shared.cache import load_cached, save_cached
from prompt_improve.shared.config import CLOUD_FALLBACK, OLLAMA_TIMEOUT, OLLAMA_URL
from prompt_improve.shared.ollama import choose_ollama_model_for_role
from prompt_improve.shared.paths import project_hint_for_prompt


def _run_ollama_models(
    role: str,
    messages: list[dict],
    cleaner: Callable[[str, str], str | None],
    prompt: str,
    cache_mode: str,
    cwd: str | None,
    temperature: float,
    num_predict: int,
    num_ctx: int,
    timeout_first: float,
    timeout_fallback: float,
) -> tuple[str, str] | None:
    """Try role-specific Ollama models in order. Returns (cleaned, source) or None."""
    if compat.ollama_client is None:
        return None
    primary, fallbacks = choose_ollama_model_for_role(role)
    if not primary:
        return None
    models = [primary] + fallbacks
    for index, model in enumerate(models):
        timeout = timeout_first if index == 0 else timeout_fallback
        try:
            content = compat.ollama_client.chat(
                messages,
                model=model,
                temperature=temperature,
                num_predict=num_predict,
                think=False,
                timeout=timeout,
                base_url=OLLAMA_URL,
                cache=False,
                num_ctx=num_ctx,
            )
        except compat.ollama_client.OllamaRequestError:
            # Model-specific failure (load failure, OOM, 404) — VRAM contention
            # makes this common with many models installed. Try the next fallback;
            # do NOT abort the whole chain (only daemon-down does that).
            continue
        except compat.ollama_client.OllamaUnavailable:
            return None
        if not content:
            continue
        cleaned = cleaner(content, prompt)
        if cleaned:
            save_cached(prompt, cache_mode, cleaned, f"ollama:{model}", cwd)
            return cleaned, f"ollama:{model}"
    return None


def call_ollama(prompt: str, cwd: str | None = None) -> tuple[str, str] | None:
    """Clarify mode: 1-3 action bullets via Ollama."""
    cached = load_cached(prompt, "clarify", cwd)
    if cached:
        return cached
    language = detect_language(prompt)
    hint = project_hint_for_prompt(prompt, cwd)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Respond in {language}.\n"
                + (f"Project context: {hint}\n" if hint else "")
                + f"\nOriginal prompt:\n{prompt}\n\n"
                "What should the agent DO or VERIFY before executing? "
                "(actions it can take with its tools — not questions for the user)"
            ),
        },
    ]
    return _run_ollama_models(
        "prompt_clarify", messages, clean_response, prompt, "clarify", cwd,
        temperature=0.15, num_predict=160, num_ctx=16384,
        timeout_first=OLLAMA_TIMEOUT, timeout_fallback=min(OLLAMA_TIMEOUT, 8.0),
    )


def call_ollama_rewrite(prompt: str, cwd: str | None = None) -> tuple[str, str] | None:
    """Rewrite mode: short/vague prompt → structured spec via Ollama."""
    cached = load_cached(prompt, "rewrite", cwd)
    if cached:
        return cached
    language = detect_language(prompt)
    hint = project_hint_for_prompt(prompt, cwd)
    messages = [
        {"role": "system", "content": build_rewrite_system_prompt(language)},
        {
            "role": "user",
            "content": (
                f"Respond and write the rewritten prompt in {language}.\n"
                + (f"Project context: {hint}\n" if hint else "")
                + f"\nOriginal prompt:\n{prompt}"
            ),
        },
    ]
    return _run_ollama_models(
        "prompt_rewrite", messages, clean_rewrite, prompt, "rewrite", cwd,
        temperature=0.2, num_predict=600, num_ctx=8192,
        timeout_first=OLLAMA_TIMEOUT, timeout_fallback=min(OLLAMA_TIMEOUT, 10.0),
    )


def call_cloud_cascade(
    prompt: str, mode: str, cwd: str | None = None,
    cloud_model: str | None = None,
) -> tuple[str, str] | None:
    """Cloud via cheap_llm cascade (cross-provider failover)."""
    if not CLOUD_FALLBACK or compat.cheap_complete is None:
        return None
    language = detect_language(prompt)
    hint = project_hint_for_prompt(prompt, cwd)
    if mode == "rewrite":
        system = build_rewrite_system_prompt(language)
        user = (
            f"Respond and write the rewritten prompt in {language}.\n"
            + (f"Project context: {hint}\n" if hint else "")
            + f"\nOriginal prompt:\n{prompt}"
        )
    else:
        system = SYSTEM_PROMPT
        user = (
            f"Respond in {language}.\n"
            + (f"Project context: {hint}\n" if hint else "")
            + f"\nOriginal prompt:\n{prompt}\n\n"
            "What should the agent DO or VERIFY before executing?"
        )
    try:
        result = compat.cheap_complete(
            system=system, prompt=user, schema_hint=None,
            timeout_total=45.0 if cloud_model else 15.0,
            prefer_local=False, require_json=False, cloud_model=cloud_model,
        )
    except Exception:
        return None
    text = (result.get("text") or "").strip() if isinstance(result, dict) else ""
    if not text:
        return None
    text = clean_rewrite(text, prompt) if mode == "rewrite" else clean_response(text, prompt)
    if not text:
        return None
    model = result.get("model") or "cloud" if isinstance(result, dict) else "cloud"
    return text, f"cloud:{model}"


def route_and_improve(
    prompt: str, mode: str, cwd: str | None
) -> tuple[str, str] | None:
    """Intelligent model router: hard → cloud first, else local first; cloud as availability fallback."""
    if needs_cloud_intelligence(prompt, mode):
        result = call_cloud_cascade(prompt, mode, cwd, cloud_model="deepseek/deepseek-v4-flash")
        if result:
            return result
    result = call_ollama_rewrite(prompt, cwd) if mode == "rewrite" else call_ollama(prompt, cwd)
    if result:
        return result
    return call_cloud_cascade(prompt, mode, cwd)
