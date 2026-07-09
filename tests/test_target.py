"""Tests for prompt_improve.features.target: TargetProfile detection and per-family format + behavior-mitigation guidance."""

from __future__ import annotations

import os


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


def test_target_profile_detects_claude_code_without_model_metadata():
    """Claude Code's UserPromptSubmit payload does not include the active model.

    The hook process does expose harness markers, so those must still select
    Claude shaping instead of silently falling back to generic Markdown.
    """
    from prompt_improve.features.target import target_profile_from_request

    keys = (
        "CLAUDECODE",
        "CLAUDE_CODE_ENTRYPOINT",
        "PROMPT_IMPROVE_TARGET_CLI",
        "PROMPT_IMPROVE_TARGET_MODEL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_BASE_URL",
        "CODEX_WORKER",
    )
    saved = {key: os.environ.get(key) for key in keys}
    codex_vars = {key: value for key, value in os.environ.items() if key.startswith("CODEX_")}
    try:
        for key in keys:
            os.environ.pop(key, None)
        for key in codex_vars:
            os.environ.pop(key, None)

        os.environ["CLAUDECODE"] = "1"
        target = target_profile_from_request({"hook_event_name": "UserPromptSubmit"})
        assert target.cli == "claude"
        assert target.family == "claude"
        assert target.style == "xml-tags"

        os.environ.pop("CLAUDECODE")
        os.environ["CLAUDE_CODE_ENTRYPOINT"] = "cli"
        target = target_profile_from_request({"hook_event_name": "UserPromptSubmit"})
        assert target.cli == "claude"
        assert target.family == "claude"
    finally:
        for key in set(keys) | set(codex_vars):
            value = saved.get(key, codex_vars.get(key))
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_target_profile_detects_claude_from_native_hook_payload():
    from prompt_improve.features.target import target_profile_from_request

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


def test_permission_mode_alone_does_not_claim_non_claude_payload():
    from prompt_improve.features.target import target_profile_from_request

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


def test_language_label_substituted_in_claude_rewrite():
    """Claude rewrite template substitutes {labels} with the user's language."""
    from prompt_improve.features.target import profile_for_model, target_guidance

    target = profile_for_model("claude-opus-4-8", "claude")
    assert "Spanish labels" in target_guidance(target, "rewrite", "Spanish")
    assert "English labels" in target_guidance(target, "rewrite", "English")
    # No literal {labels} token must leak into the rendered guidance.
    assert "{labels}" not in target_guidance(target, "rewrite", "English")
