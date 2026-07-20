"""Tests for prompt_improve.features.target: TargetProfile detection and per-family format + behavior-mitigation guidance."""

from __future__ import annotations

import os

# Env vars read by target_profile_from_request's model/cli detection. Scrubbing
# them makes detection tests deterministic under any proxy backend — e.g. a GLM
# proxy sets ANTHROPIC_MODEL + CLAUDE_AGENT_IDENTITY, which would otherwise win
# over a bare hook payload and misclassify the family/cli as 'glm'/'zai'.
_TARGET_SCRUB_VARS = (
    "PROMPT_IMPROVE_TARGET_CLI",
    "CODEX_TARGET_CLI",
    "CLAUDE_TARGET_CLI",
    "CLI_ORCHESTRATION_CALLER",
    "PROMPT_IMPROVE_TARGET_MODEL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_MODEL",
    "CLAUDE_AGENT_IDENTITY",
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CODEX_MODEL",
    "OPENAI_MODEL",
    "OPENAI_API_MODEL",
    "GEMINI_MODEL",
    "GOOGLE_MODEL",
    "AGY_MODEL",
    "AGY_SETTINGS",
    "DEEPSEEK_MODEL",
    "QWEN_MODEL",
    "KIMI_MODEL",
    "MINIMAX_MODEL",
    "ZAI_MODEL",
    "GLM_MODEL",
    "GROK_MODEL",
    "XAI_MODEL",
    "GROK_AGENT",
    "MODEL_NAME",
    "MODEL_ID",
    "MODEL",
    "CODEX_WORKER",
)


def _scrub_target_env(monkeypatch) -> None:
    """Remove every env var that target_profile_from_request reads for model/cli
    detection. Includes prefix-scoped harness markers (CODEX_*, CLAUDE_CODE_*):
    ``_cli_from_env_or_model`` short-circuits to 'codex' on ANY residual CODEX_*
    before it ever checks the claude markers, so listing individual CODEX_ vars
    is not enough — the whole prefix must be scrubbed (the original test did this)."""
    for key in _TARGET_SCRUB_VARS:
        monkeypatch.delenv(key, raising=False)
    for key in list(os.environ):
        if key.startswith("CODEX_") or key.startswith("CLAUDE_CODE_"):
            monkeypatch.delenv(key, raising=False)


def test_target_profile_classifies_primary_cli_models():
    from prompt_improve.features.target import profile_for_model

    assert profile_for_model("claude-opus-4-8", "claude").family == "claude"
    assert profile_for_model("claude-sonnet-5", "claude").style == "xml-tags"
    assert profile_for_model("claude-fable-5", "claude").family == "claude"
    assert profile_for_model("gpt-5.5", "codex").family == "openai-gpt"
    assert profile_for_model("gpt-5.5", "codex").style == "gpt5-outcome-first"
    assert profile_for_model("gpt-5.6", "codex").version == "5.6"
    assert profile_for_model("gpt-5.4-mini", "codex").family == "openai-gpt"
    assert profile_for_model("Gemini 3.5 Flash (High)", "antigravity").family == "gemini"
    assert (
        profile_for_model("Gemini 3.5 Flash (High)", "antigravity").style
        == "gemini3-concise-blocks"
    )
    assert profile_for_model("Gemini 3.5 Pro (High)", "antigravity").family == "gemini"


def test_target_profile_classifies_proxy_shell_models():
    from prompt_improve.features.target import profile_for_model

    assert profile_for_model("MiniMax-M3[1m]", "mini").family == "minimax"
    assert profile_for_model("kimi-2.7-code", "kimi").family == "kimi"
    assert profile_for_model("mimo-2.5-pro", "mimo").family == "mimo"
    assert profile_for_model("deepseek-v4-pro[1m]", "dseek").family == "deepseek"
    assert profile_for_model("glm-5.2[1m]", "zai").family == "glm"
    assert profile_for_model("qwen3.7-max[1m]", "qwen").family == "qwen"
    assert profile_for_model("grok-4.5", "grok").family == "grok"
    assert profile_for_model("grok-4.5", "grok").style == "grok-4.5-agentic"
    assert profile_for_model("x-ai/grok-4.5", "codex").family == "grok"


def test_target_profile_explicit_model_beats_codex_cli_fallback():
    from prompt_improve.features.target import profile_for_model

    assert profile_for_model("MiniMax-M3[1m]", "codex").family == "minimax"
    assert profile_for_model("kimi-k2.7-code", "codex").family == "kimi"
    assert profile_for_model("deepseek-v4-flash", "codex").family == "deepseek"


def test_target_profile_classifies_proxy_cli_without_model():
    from prompt_improve.features.target import profile_for_model

    assert profile_for_model("unknown", "mini").family == "minimax"
    assert profile_for_model("unknown", "kimi").family == "kimi"
    assert profile_for_model("unknown", "dseek").family == "deepseek"
    assert profile_for_model("unknown", "qwen").family == "qwen"
    assert profile_for_model("unknown", "zai").family == "glm"
    assert profile_for_model("unknown", "mimo").family == "mimo"
    assert profile_for_model("unknown", "grok").family == "grok"
    assert profile_for_model("unknown", "grok-build").family == "grok"


def test_target_profile_reads_common_model_envs():
    from prompt_improve.features.target import target_profile_from_request

    keys = (
        "PROMPT_IMPROVE_TARGET_MODEL",
        "CODEX_MODEL",
        "OPENAI_MODEL",
        "OPENAI_API_MODEL",
        "CLAUDE_MODEL",
        "ANTHROPIC_MODEL",
        "GEMINI_MODEL",
        "GOOGLE_MODEL",
        "AGY_MODEL",
        "DEEPSEEK_MODEL",
        "QWEN_MODEL",
        "KIMI_MODEL",
        "MINIMAX_MODEL",
        "ZAI_MODEL",
        "GLM_MODEL",
        "MODEL_NAME",
        "MODEL_ID",
        "MODEL",
    )
    saved = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ["MINIMAX_MODEL"] = "MiniMax-M3[1m]"
        target = target_profile_from_request({})
        assert target.family == "minimax"
        assert target.style == "minimax-m3-longctx"
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_target_profile_detects_claude_code_without_model_metadata(monkeypatch):
    """Claude Code's UserPromptSubmit payload does not include the active model.

    The hook process does expose harness markers, so those must still select
    Claude shaping instead of silently falling back to generic Markdown.
    """
    from prompt_improve.features.target import target_profile_from_request

    _scrub_target_env(monkeypatch)

    monkeypatch.setenv("CLAUDECODE", "1")
    target = target_profile_from_request({"hook_event_name": "UserPromptSubmit"})
    assert target.cli == "claude"
    assert target.family == "claude"
    assert target.style == "xml-tags"

    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    target = target_profile_from_request({"hook_event_name": "UserPromptSubmit"})
    assert target.cli == "claude"
    assert target.family == "claude"


def test_target_profile_uses_orchestration_pipeline_caller(monkeypatch):
    from prompt_improve.features.target import target_profile_from_request

    _scrub_target_env(monkeypatch)
    for caller, family in (
        ("claude", "claude"),
        ("codex", "openai-gpt"),
        ("gemini", "gemini"),
        ("antigravity", "gemini"),
        ("grok", "grok"),
    ):
        monkeypatch.setenv("CLI_ORCHESTRATION_CALLER", caller)
        target = target_profile_from_request({"hook_event_name": "UserPromptSubmit"})
        assert target.cli == caller
        assert target.family == family


def test_target_profile_detects_grok_agent_env(monkeypatch):
    """Native Grok Build sessions export GROK_AGENT (often '1').

    Without this harness marker the hook falls through to generic Markdown and
    wastes the target-aware shaping path that every other CLI already gets.
    """
    from prompt_improve.features.target import target_profile_from_request

    _scrub_target_env(monkeypatch)
    monkeypatch.setenv("GROK_AGENT", "1")
    target = target_profile_from_request({"hook_event_name": "UserPromptSubmit"})
    assert target.cli == "grok"
    assert target.family == "grok"
    assert "grok" in target.style

    monkeypatch.delenv("GROK_AGENT", raising=False)
    monkeypatch.setenv("GROK_MODEL", "grok-4.5")
    target = target_profile_from_request({})
    assert target.family == "grok"
    assert target.model == "grok-4.5"
    assert target.style == "grok-4.5-agentic"


def test_target_profile_detects_claude_from_native_hook_payload(monkeypatch):
    """A native Claude Code hook payload (UserPromptSubmit + transcript_path)
    resolves to the claude family. Scrub every model/cli env var first so the
    test is deterministic under any proxy backend — e.g. ANTHROPIC_MODEL=glm-5.2
    set by a GLM proxy would otherwise win over the payload and misclassify the
    family as 'glm' (correct behavior in production, wrong for THIS assertion)."""
    from prompt_improve.features.target import target_profile_from_request

    _scrub_target_env(monkeypatch)

    payload = {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "improve error handling",
        "cwd": "/tmp/project",
        "transcript_path": "/tmp/transcript.jsonl",
        "permission_mode": "plan",
    }
    target = target_profile_from_request(payload)
    assert target.cli == "claude"
    assert target.family == "claude"
    assert target.style == "xml-tags"


def test_shape_by_cli_overrides_model_family(monkeypatch):
    """PROMPT_IMPROVE_SHAPE_BY=cli shapes for the CLI family, not the underlying
    proxy model (e.g. Claude Code on a GLM backend -> claude XML tags, not glm).
    The real model is still carried for cache partitioning and version notes.
    Default (model) keeps shaping for the model family."""
    from prompt_improve.features.target import profile_for_cli, target_profile_from_request

    _scrub_target_env(monkeypatch)

    monkeypatch.setenv("PROMPT_IMPROVE_SHAPE_BY", "cli")
    target = target_profile_from_request({"cli": "claude", "model": "glm-5.2[1m]"})
    assert target.cli == "claude"
    assert target.family == "claude"
    assert target.style == "xml-tags"
    assert target.model == "glm-5.2[1m]"

    # default (model) still resolves to the underlying model family
    monkeypatch.delenv("PROMPT_IMPROVE_SHAPE_BY", raising=False)
    target = target_profile_from_request({"cli": "claude", "model": "glm-5.2[1m]"})
    assert target.family == "glm"

    # direct helper: CLI drives family; unknown CLI falls back to generic
    assert profile_for_cli("claude", "glm-5.2[1m]").family == "claude"
    assert profile_for_cli("codex", "glm-5.2[1m]").family == "openai-gpt"
    assert profile_for_cli("qwenc", "unknown").family == "generic"
    assert profile_for_cli("weird-cli", "x").family == "generic"


def test_permission_mode_alone_does_not_claim_non_claude_payload(monkeypatch):
    """permission_mode alone does NOT imply Claude CLI.

    Other env vars (e.g. ANTHROPIC_MODEL) must be scrubbed so env-based
    detection does not win over the bare payload — the test is asserting that
    ``permission_mode`` in the payload is NOT a Claude CLI signal.
    """
    from prompt_improve.features.target import target_profile_from_request

    for var in _TARGET_SCRUB_VARS:
        monkeypatch.delenv(var, raising=False)
    target = target_profile_from_request(
        {
            "hook_event_name": "UserPromptSubmit",
            "permission_mode": "plan",
            "prompt": "improve error handling",
        }
    )
    assert target.cli != "claude"


def test_build_messages_uses_claude_xml_guidance():
    import prompt_improve.features.improve as m
    from prompt_improve.features.target import profile_for_model

    target = profile_for_model("claude-opus-4-8", "claude")
    system, _ = m._build_messages("rewrite", "fix the bug", None, target)
    assert "Claude family" in system
    assert "<task>" in system
    assert "<acceptance>" in system


def test_build_messages_uses_codex_markdown_guidance():
    import prompt_improve.features.improve as m
    from prompt_improve.features.target import profile_for_model

    target = profile_for_model("gpt-5.5", "codex")
    system, _ = m._build_messages("rewrite", "fix the bug", None, target)
    assert "OpenAI GPT/Codex" in system
    assert "Markdown sections" in system
    assert "outcome-first prompts" in system
    assert "GPT-5.x" in system
    assert "allowed side effects" in system
    assert "smallest useful check" in system
    assert "do not use XML" in system


def test_gpt56_variants_use_prioritization_not_generic_brevity():
    import prompt_improve.features.improve as m
    from prompt_improve.features.target import profile_for_model

    for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
        target = profile_for_model(model, "codex")
        system, _ = m._build_messages("rewrite", "fix the bug", None, target)
        assert "prioritize required facts" in system
        assert "over generic brevity" in system


def test_build_messages_uses_gemini_component_guidance():
    import prompt_improve.features.improve as m
    from prompt_improve.features.target import profile_for_model

    target = profile_for_model("Gemini 3.5 Flash (High)", "antigravity")
    system, _ = m._build_messages("rewrite", "fix the bug", None, target)
    assert "Gemini/Antigravity" in system
    assert "Objective" in system
    assert "Output format" in system
    assert "concise, direct instructions" in system


def test_build_messages_uses_grok_markdown_guidance():
    import prompt_improve.features.improve as m
    from prompt_improve.features.target import profile_for_model

    target = profile_for_model("grok-4.5", "grok")
    system, _ = m._build_messages("rewrite", "fix the bug", None, target)
    assert "Grok" in system
    assert "GitHub-flavored" in system
    assert "always-approve" in system
    assert "Grok 4.5" in system
    # Markdown path — not Claude XML section tags as primary structure.
    assert "<task>" not in system


_FAMILY_CASES = [
    ("claude", "claude-opus-4-8", "claude"),
    ("openai-gpt", "gpt-5.5", "codex"),
    ("gemini", "Gemini 3.5 Flash (High)", "antigravity"),
    ("qwen", "qwen3.7-max[1m]", "qwen"),
    ("deepseek", "deepseek-v4-pro[1m]", "dseek"),
    ("glm", "glm-5.2[1m]", "zai"),
    ("minimax", "MiniMax-M3[1m]", "mini"),
    ("kimi", "kimi-2.7-code", "kimi"),
    ("mimo", "mimo-2.5-pro", "mimo"),
    ("gemma", "gemma-4-12b-it-qat", "generic"),
    ("grok", "grok-4.5", "grok"),
]


def test_target_guidance_distinct_per_family():
    """No two families may share the same rewrite guidance signature."""
    from prompt_improve.features.target import profile_for_model, target_guidance

    sigs = {}
    for family, model, cli in _FAMILY_CASES:
        target = profile_for_model(model, cli)
        assert target.family == family
        sigs[family] = target_guidance(target, "rewrite", "English")[:60]
    duplicates = [k for k, v in sigs.items() if list(sigs.values()).count(v) > 1]
    assert not duplicates, f"families share guidance signatures: {duplicates}"


def test_behavior_hints_present_per_family():
    """Each family's characteristic failure-mode keyword must appear in guidance."""
    from prompt_improve.features.target import profile_for_model, target_guidance

    behavior_keywords = {
        "qwen": "failed command",
        "glm": "PATH",
        "minimax": "exploration loop",
        "kimi": "subagent",
        "deepseek": "reasoning",
        "mimo": "sequential",
        "claude": "over-exploration",
        "openai-gpt": "FILES",
        "gemini": "dilutes focus",
        "grok": "always-approve",
    }
    family_to_case = {f: (m, c) for f, m, c in _FAMILY_CASES}
    for family, keyword in behavior_keywords.items():
        model, cli = family_to_case[family]
        guidance = target_guidance(profile_for_model(model, cli), "rewrite", "English")
        assert keyword in guidance, f"{family} missing behavior keyword {keyword!r}"


def test_generic_family_has_no_behavior_mitigation():
    """Generic is the unprofiled fallback — it must not inject a fake mitigation."""
    from prompt_improve.features.target import profile_for_model, target_guidance

    target = profile_for_model("some-unknown-model-xyz", "generic")
    guidance = target_guidance(target, "rewrite", "English")
    assert "Mitigation" not in guidance


def test_clarify_mode_also_includes_behavior():
    """Behavior mitigations apply in clarify mode too (a model's pattern is mode-independent)."""
    from prompt_improve.features.target import profile_for_model, target_guidance

    target = profile_for_model("qwen3.7-max[1m]", "qwen")
    clarify = target_guidance(target, "clarify", "English")
    assert "failed command" in clarify


def test_deepseek_guidance_does_not_request_hidden_cot():
    from prompt_improve.features.target import profile_for_model, target_guidance

    guidance = target_guidance(
        profile_for_model("deepseek-v4-flash", "dseek"), "rewrite", "English"
    )
    assert "do not request hidden chain-of-thought" in guidance


def test_target_profile_detects_deepseek_r1_as_reasoner():
    """R1 / deepseek-reasoner is a pure reasoning model distinct from V3/V4 instruct.

    Family stays 'deepseek' (shared guidance registry), but the style label must
    flag the reasoner lineage so cache_key partitions it and _variant_guidance can
    apply R1-specific shaping (no system prompt, zero-shot, temp ~0.6).
    Source: DeepSeek-R1 README (api-docs.deepseek.com).
    """
    from prompt_improve.features.target import profile_for_model

    for model in ("deepseek-r1", "deepseek-reasoner", "DeepSeek-R1-Distill"):
        target = profile_for_model(model, "dseek")
        assert target.family == "deepseek", f"{model} family drifted"
        assert target.style == "deepseek-r1-reasoner", f"{model} not flagged as reasoner"


def test_deepseek_r1_guidance_is_reasoner_specific():
    """R1 guidance must carry the README-mandated reasoner constraints, and must
    NOT carry the V4 instruct note (the two lineages are mutually exclusive)."""
    from prompt_improve.features.target import profile_for_model, target_guidance

    guidance = target_guidance(
        profile_for_model("deepseek-reasoner", "dseek"), "rewrite", "English"
    )
    assert "do NOT use a system prompt" in guidance
    assert "zero-shot" in guidance
    assert "temperature 0.5-0.7" in guidance
    # R1 must not get the V4 variant note (distinct lineage)
    assert "DeepSeek V4 is strong for coding" not in guidance


def test_language_label_substituted_in_claude_rewrite():
    """Claude rewrite template substitutes {labels} with the user's language."""
    from prompt_improve.features.target import profile_for_model, target_guidance

    target = profile_for_model("claude-opus-4-8", "claude")
    assert "Spanish labels" in target_guidance(target, "rewrite", "Spanish")
    assert "English labels" in target_guidance(target, "rewrite", "English")
    # No literal {labels} token must leak into the rendered guidance.
    assert "{labels}" not in target_guidance(target, "rewrite", "English")
