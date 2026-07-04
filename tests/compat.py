"""Compatibility shim — re-exports all symbols tests expect from the old monolith.

Tests import this as ``ip`` to get the same interface as the old
``improve-prompt.py`` hook module.
"""
from prompt_improve.shared.config import (  # noqa: F401
    OLLAMA_MODEL_CANDIDATES,
    _ROLE_MODEL_MAP,
    REWRITE_THRESHOLD,
    CACHE_TTL_SECONDS,
    CLOUD_FALLBACK,
)
from prompt_improve.shared.ollama import (  # noqa: F401
    available_ollama_models,
    start_ollama_best_effort,
    choose_ollama_model_for_role,
)
from prompt_improve.shared.cache import (  # noqa: F401
    _cache_key,
    load_cached,
    save_cached,
)
from prompt_improve.shared.paths import (  # noqa: F401
    project_hint as _project_hint,
    project_hint_for_prompt as _project_hint_for_prompt,
    project_current_task_line,
    current_task_hint_line,
    should_include_task_hint,
)
from prompt_improve.features.detect import (  # noqa: F401
    detect_trivial,
    detect_language,
    has_concrete_target,
    decide_mode,
)
from prompt_improve.features.classify import needs_cloud_intelligence  # noqa: F401
from prompt_improve.features.clean import (  # noqa: F401
    clean_rewrite as _clean_rewrite,
    clean_response as _clean_response,
    soften_invented_absolutes as _soften_invented_absolutes,
    trim_bullet as _trim_bullet,
    remove_long_examples as _remove_long_examples,
    sanitize_bullet as _sanitize_bullet,
)
from prompt_improve.features.rules import (  # noqa: F401
    build_rewrite_system_prompt,
    rule_based_suggestions,
)
from prompt_improve.features.hints import continuation_context as _continuation_context  # noqa: F401
from prompt_improve.features.improve import (  # noqa: F401
    call_ollama_rewrite,
    call_ollama,
    call_cloud_cascade,
    route_and_improve as _route_and_improve,
)

# Attribute-style access aliases (tests use ip._project_hint, ip._cache_key, etc.)
__file__ = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src" / "prompt_improve" / "__init__.py")
