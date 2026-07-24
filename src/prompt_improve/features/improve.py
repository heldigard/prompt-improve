# vs-soft-allow: nesting_depth — for/try/if is the natural shape of retry loops over model APIs; params are config for a generic model-runner
"""LLM calls: Ollama clarify/rewrite, cloud cascade, intelligent router."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from time import monotonic

from prompt_improve.features.classify import needs_cloud_intelligence
from prompt_improve.features.clean import clean_response, clean_rewrite
from prompt_improve.features.detect import detect_language
from prompt_improve.features.hints import project_hint_for_prompt
from prompt_improve.features.rules import SYSTEM_PROMPT, build_rewrite_system_prompt
from prompt_improve.features.target import (
    GENERIC_TARGET,
    TargetProfile,
    target_guidance,
    target_profile_from_request,
)
from prompt_improve.shared import compat, metrics
from prompt_improve.shared.cache import load_cached, save_cached
from prompt_improve.shared.config import (
    CLOUD_FALLBACK,
    OLLAMA_TIMEOUT,
    OLLAMA_TOTAL_TIMEOUT,
    OLLAMA_URL,
)
from prompt_improve.shared.ollama import choose_ollama_model_for_role

_DEBUG = os.environ.get("OLLAMA_IMPROVE_DEBUG", "0") == "1"


def _debug(msg: str) -> None:
    if _DEBUG:
        print(f"[prompt-improve] {msg}", file=sys.stderr)


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
    deadline: float | None = None,
) -> tuple[str, str] | None:
    """Try role-specific Ollama models in order. Returns (cleaned, source) or None."""
    if compat.ollama_client is None:
        _debug("ollama_client not available")
        return None
    primary, fallbacks = choose_ollama_model_for_role(role)
    if not primary:
        _debug(f"no model available for role={role}")
        return None
    # Cap the chain (primary + 5 fallbacks) so a slow/hung daemon can't walk the
    # full available-model tail (60+) — bounds worst-case latency before the
    # cloud fallback kicks in. The role map's explicit candidates come first, so
    # the cap rarely truncates a preferred model.
    models = ([primary] + fallbacks)[:6]
    _debug(f"role={role} chain={[m.split(':')[0] for m in models]}")
    deadline = deadline if deadline is not None else monotonic() + OLLAMA_TOTAL_TIMEOUT
    for index, model in enumerate(models):
        remaining = deadline - monotonic()
        if remaining < 0.1:
            _debug(f"role={role} exhausted shared improvement budget")
            break
        per_model_timeout = timeout_first if index == 0 else timeout_fallback
        timeout = min(per_model_timeout, remaining)
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
            _debug(f"  model={model} load-fail (VRAM/OOM), trying next")
            continue
        except compat.ollama_client.OllamaUnavailable:
            _debug("daemon down, aborting chain")
            return None
        except Exception as exc:
            # The optional helper evolves independently. An unexpected
            # transport/response exception must degrade to cloud/rules rather
            # than abort the whole UserPromptSubmit pipeline.
            _debug(f"ollama client error ({type(exc).__name__}), aborting local chain")
            return None
        if not content:
            _debug(f"  model={model} returned empty")
            continue
        cleaned = cleaner(content, prompt)
        if cleaned:
            _debug(f"  model={model} OK ({len(cleaned)} chars)")
            save_cached(prompt, cache_mode, cleaned, f"ollama:{model}", cwd)
            metrics.record("ollama")
            return cleaned, f"ollama:{model}"
        _debug(f"  model={model} cleaner rejected output")
    _debug(f"exhausted chain for role={role}")
    return None


def _cache_mode(mode: str, target: TargetProfile) -> str:
    return f"{mode}:{target.cache_key}"


def _cloud_cache_mode(mode: str, target: TargetProfile, cloud_model: str) -> str:
    """Partition hard-route cache entries when the configured cloud model changes."""
    return f"{_cache_mode(mode, target)}:cloud:{cloud_model}"


def _build_messages(
    mode: str,
    prompt: str,
    cwd: str | None,
    target: TargetProfile = GENERIC_TARGET,
) -> tuple[str, str]:
    """Compose (system_prompt, user_message) for a given mode.

    Shared across call_ollama / call_ollama_rewrite / call_cloud_cascade so the
    language hint + project anchor stay in one place. Returns plain (system, user)
    strings; the caller wraps them in the chat-message shape its backend expects.
    """
    language = detect_language(prompt)
    hint = project_hint_for_prompt(prompt, cwd, language)
    hint_line = f"Execution context (not task scope): {hint}\n" if hint else ""
    if mode == "rewrite":
        system = build_rewrite_system_prompt(language, target)
        user = f"Respond and write the rewritten prompt in {language}.\n{hint_line}\nOriginal prompt:\n{prompt}"
    else:
        system = SYSTEM_PROMPT + target_guidance(target, "clarify", language) + "\n"
        user = (
            f"Respond in {language}.\n{hint_line}\nOriginal prompt:\n{prompt}\n\n"
            "What should the agent DO or VERIFY before executing? "
            "(actions it can take with its tools — not questions for the user)"
        )
    return system, user


def call_ollama(
    prompt: str,
    cwd: str | None = None,
    target: TargetProfile | None = None,
    deadline: float | None = None,
) -> tuple[str, str] | None:
    """Clarify mode: 1-3 action bullets via Ollama."""
    target = target or target_profile_from_request()
    cache_mode = _cache_mode("clarify", target)
    cached = load_cached(prompt, cache_mode, cwd)
    if cached:
        metrics.record("cache:hit")
        return cached
    system, user = _build_messages("clarify", prompt, cwd, target)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return _run_ollama_models(
        "prompt_clarify",
        messages,
        clean_response,
        prompt,
        cache_mode,
        cwd,
        temperature=0.15,
        num_predict=160,
        num_ctx=16384,
        timeout_first=OLLAMA_TIMEOUT,
        timeout_fallback=min(OLLAMA_TIMEOUT, 30.0),
        deadline=deadline,
    )


def call_ollama_rewrite(
    prompt: str,
    cwd: str | None = None,
    target: TargetProfile | None = None,
    deadline: float | None = None,
) -> tuple[str, str] | None:
    """Rewrite mode: short/vague prompt → structured spec via Ollama."""
    target = target or target_profile_from_request()
    cache_mode = _cache_mode("rewrite", target)
    cached = load_cached(prompt, cache_mode, cwd)
    if cached:
        metrics.record("cache:hit")
        return cached
    system, user = _build_messages("rewrite", prompt, cwd, target)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return _run_ollama_models(
        "prompt_rewrite",
        messages,
        clean_rewrite,
        prompt,
        cache_mode,
        cwd,
        temperature=0.2,
        # The cleaner accepts at most 140 words / 900 chars. Keep generation
        # bounded too, so rejected verbosity does not burn the interactive
        # hook's local-model budget.
        num_predict=320,
        num_ctx=8192,
        timeout_first=OLLAMA_TIMEOUT,
        timeout_fallback=min(OLLAMA_TIMEOUT, 30.0),
        deadline=deadline,
    )


def call_cloud_cascade(
    prompt: str,
    mode: str,
    cwd: str | None = None,
    cloud_model: str | None = None,
    target: TargetProfile | None = None,
    deadline: float | None = None,
) -> tuple[str, str] | None:
    """Cloud via cheap_llm cascade (cross-provider failover)."""
    if not CLOUD_FALLBACK or compat.cheap_complete is None:
        _debug("cloud cascade disabled or cheap_llm unavailable")
        return None
    deadline = deadline if deadline is not None else monotonic() + OLLAMA_TOTAL_TIMEOUT
    remaining = deadline - monotonic()
    if remaining < 0.1:
        _debug("cloud cascade skipped: shared improvement budget exhausted")
        return None
    target = target or target_profile_from_request()
    system, user = _build_messages(mode, prompt, cwd, target)
    try:
        result = compat.cheap_complete(
            system=system,
            prompt=user,
            schema_hint=None,
            timeout_total=min(45.0 if cloud_model else 15.0, remaining),
            prefer_local=False,
            require_json=False,
            cloud_model=cloud_model,
        )
    except (OSError, ValueError, TypeError, KeyError):
        # Transient/network/data-shape failures from the cloud cascade — fail OPEN
        # (return None → caller falls back to local). Programmer errors (NameError,
        # AttributeError) intentionally bubble up so they surface in tests.
        _debug("cloud cascade raised transient error")
        return None
    text = (result.get("text") or "").strip() if isinstance(result, dict) else ""
    if not text:
        return None
    text = clean_rewrite(text, prompt) if mode == "rewrite" else clean_response(text, prompt)
    if not text:
        return None
    model = (result.get("model") or "cloud") if isinstance(result, dict) else "cloud"
    metrics.record("cloud")
    return text, f"cloud:{model}"


def route_and_improve(
    prompt: str,
    mode: str,
    cwd: str | None,
    target: TargetProfile | None = None,
    deadline: float | None = None,
) -> tuple[str, str] | None:
    """Intelligent model router: hard → cloud first, else local first; cloud as availability fallback."""
    deadline = deadline if deadline is not None else monotonic() + OLLAMA_TOTAL_TIMEOUT
    target = target or target_profile_from_request()
    if needs_cloud_intelligence(prompt, mode):
        # Read at call time (like the classifier's toggle) so tests and shell
        # wrappers can override without reloading the module.
        cloud_model = (
            os.environ.get("OLLAMA_IMPROVE_CLOUD_MODEL", "").strip() or "deepseek/deepseek-v4-flash"
        )
        # Hard prompts bypass call_ollama[_rewrite], which normally owns the
        # cache lookup/save path. Check the same target-specific key here so a
        # repeated security/architecture prompt does not pay for another cloud
        # call merely because cloud is the preferred first route. Include the
        # improving cloud model: an explicit model override must not reuse a
        # result produced by the previous provider/model.
        cache_mode = _cloud_cache_mode(mode, target, cloud_model)
        if CLOUD_FALLBACK:
            cached = load_cached(prompt, cache_mode, cwd)
            if cached:
                metrics.record("cache:hit")
                return cached
        _debug(f"hard prompt → cloud-first ({cloud_model})")
        result = call_cloud_cascade(
            prompt,
            mode,
            cwd,
            cloud_model=cloud_model,
            target=target,
            deadline=deadline,
        )
        if result:
            save_cached(prompt, cache_mode, result[0], result[1], cwd)
            return result
        _debug("cloud-first failed, falling back to local")
    _debug(f"trying local ({mode})")
    result = (
        call_ollama_rewrite(prompt, cwd, target, deadline=deadline)
        if mode == "rewrite"
        else call_ollama(prompt, cwd, target, deadline=deadline)
    )
    if result:
        return result
    _debug("local unavailable, trying cloud availability fallback")
    return call_cloud_cascade(prompt, mode, cwd, target=target, deadline=deadline)
