"""Per-family prompt-shape knowledge (format + behavior).

The "what" axis of target-awareness: for each model family, the prompt-shape
guidance the improved prompt should follow. This is declarative knowledge — it
changes when we learn new facts about a family (new format preference, new
failure-mode), not when detection changes.

Two dimensions per family:
- **format** (`rewrite` / `clarify`): how to STRUCTURE the improved prompt
  (XML tags vs Markdown vs component blocks). Stable, low churn.
- **behavior**: a failure-mode MITIGATION specific to that family's known
  pattern (qwen blind-retries failed commands; glm loses PATH across shell
  calls; minimax exploration-loops; kimi forces its model on subagents; etc).
  Sourced from `~/.claude/rules/model-specific.md`. Higher churn.

Both are looked up by `family` (the dispatch key set in `profile.profile_for_model`)
and composed by `target_guidance`. Dict dispatch replaces the prior if/elif chain.

Note: the previously-collapsed families (qwen, deepseek, glm, minimax, kimo,
mimo) each get distinct format AND behavior here — the old `_literal_guidance`
applied the same generic text to all six despite their opposite failure-modes.
"""

from __future__ import annotations

from dataclasses import dataclass

from prompt_improve.features.target.profile import TargetProfile


@dataclass(frozen=True)
class FamilyShape:
    """Prompt-shape knowledge for one model family.

    `rewrite`/`clarify` are format templates; a literal ``{labels}`` token is
    substituted with the user's language label ("Spanish labels"/"English labels").
    `behavior` is a failure-mode mitigation appended in BOTH modes (a model's
    behavioral pattern is independent of prompt mode); empty string means none.
    """

    family: str
    rewrite: str
    clarify: str
    behavior: str = ""


def target_guidance(target: TargetProfile, mode: str, language: str) -> str:
    """Format + behavior guidance for the target's family, composed for `mode`."""
    shape = SHAPES.get(target.family, SHAPES["generic"])
    template = shape.rewrite if mode == "rewrite" else shape.clarify
    guidance = _render(template, language)
    variant = _variant_guidance(target)
    if variant:
        guidance = f"{guidance} {variant}"
    if shape.behavior:
        guidance = f"{guidance} {shape.behavior}"
    return guidance


def _render(template: str, language: str) -> str:
    """Substitute ``{labels}`` with the language label.

    `str.replace` (not `str.format`) so literal braces in a future template
    cannot break rendering.
    """
    labels = "Spanish labels" if language == "Spanish" else "English labels"
    return template.replace("{labels}", labels)


def _variant_guidance(target: TargetProfile) -> str:
    """Small current-model notes layered over broad family guidance."""
    lower = target.model.lower()
    if target.family == "openai-gpt":
        notes = []
        if "gpt-5.5" in lower or target.style == "gpt5-outcome-first":
            notes.append(
                "Version note: GPT-5.x responds best to outcome-first prompts: "
                "goal, constraints, success criteria, allowed side effects, "
                "evidence rules, and output shape; avoid prescribing every "
                "intermediate step unless the path matters."
            )
        if target.version.startswith("5.6"):
            notes.append(
                "GPT-5.6 note: prioritize required facts, evidence, decisions, and next actions "
                "over generic brevity. Keep the prompt and tool guidance lightweight; add detail "
                "only for a task-specific requirement."
            )
        if target.cli == "codex" or "codex" in lower:
            notes.append(
                "Codex note: include relevant files/context when known, plan first "
                "for difficult work, describe evidence crisply, parallelize independent "
                "reads, and verify with the smallest useful check."
            )
        return " ".join(notes)
    if target.family == "claude" and any(token in lower for token in ("opus", "fable", "sonnet")):
        return (
            "Version note: use consistent, descriptive XML tags and keep examples, "
            "context, inputs, and instructions in separate tagged regions."
        )
    if target.family == "gemini" and ("gemini 3" in lower or "gemini-3" in lower):
        return (
            "Version note: Gemini 3 responds best to concise, direct instructions; "
            "for long context, place the data/context first and anchor the final "
            "request after it with an explicit output format."
        )
    if target.family == "deepseek":
        if "r1" in lower or "reasoner" in lower:
            return (
                "Version note: DeepSeek-R1 / deepseek-reasoner is a pure reasoning "
                "model. Put ALL instructions in the user message and do NOT use a "
                "system prompt (it was trained without one). Prefer zero-shot — "
                "avoid few-shot examples, which degrade its reasoning chain. Use "
                "temperature 0.5-0.7 (0.6 recommended). Keep the prompt concise; "
                "do not request visible chain-of-thought."
            )
        if "v4" in lower:
            return (
                "Version note: DeepSeek V4 is strong for coding and agentic reasoning; "
                "keep externally visible steps numbered, specify the final answer "
                "contract, and do not request hidden chain-of-thought."
            )
    if target.family == "qwen" and ("qwen3" in lower or "qwen-3" in lower):
        return (
            "Version note: Qwen3 prompts should be self-contained and literal; "
            "avoid relying on follow-up dialogue to fill missing task constraints."
        )
    if target.family == "minimax" and ("m3" in lower or target.style == "minimax-m3-longctx"):
        return (
            "Version note: MiniMax M3 supports long agentic/coding context, but the "
            "prompt should still name the first artifact and a stop condition."
        )
    if target.family == "kimi" and ("2.7" in lower or "k2.7" in lower):
        return (
            "Version note: Kimi K2.7 Code is code-focused with thinking behavior "
            "already on; keep coding tasks self-contained and acceptance-driven."
        )
    return ""


# ---- registry --------------------------------------------------------------

SHAPES: dict[str, FamilyShape] = {
    "claude": FamilyShape(
        family="claude",
        rewrite=(
            "Target model profile: Claude family. Output the rewritten prompt with "
            "short XML-style sections using stable tags such as <task>, <context>, "
            "<constraints>, and <acceptance>. Keep human-visible text in the user's "
            "language ({labels}). Put context before the final task when source "
            "material is present. Do not wrap the whole answer in markdown fences."
        ),
        clarify=(
            "Target model profile: Claude family. Use concise bullets and, where a "
            "bullet names separate material, prefer XML tag names like <context> or "
            "<acceptance> so Claude can parse instructions, context, and input cleanly."
        ),
        behavior=(
            "Mitigation: state ONE imperative objective — vague scope triggers "
            "over-exploration. Separate <context> from <instructions> so source "
            "material is not conflated with directives. End with a verification the "
            "agent performs, chosen for the task (source comparison, focused test, or reference check)."
        ),
    ),
    "openai-gpt": FamilyShape(
        family="openai-gpt",
        rewrite=(
            "Target model profile: OpenAI GPT/Codex. Output clean Markdown sections "
            "with an outcome-first contract, concrete evidence or verification "
            "rules when inferable, and backticks around file paths/functions/classes. "
            "Separate instructions from the user's original input; do not use XML."
        ),
        clarify=(
            "Target model profile: OpenAI GPT/Codex. Use 1-3 Markdown bullets that "
            "name concrete actions, verification, and any TODO/planning need. Use "
            "backticks for paths/functions/classes. Do not use XML."
        ),
        behavior=(
            "Mitigation: structure the spec around FILES / CONTRACT / CONSTRAINTS / "
            "EVIDENCE / ACCEPTANCE — GPT/Codex follows explicit success criteria "
            "and stopping rules better than open prose."
        ),
    ),
    "gemini": FamilyShape(
        family="gemini",
        rewrite=(
            "Target model profile: Gemini/Antigravity. Output clearly labeled "
            "component blocks: Objective, Instructions, Context, Constraints, and "
            "Output format, using only blocks that are inferable. Keep the user's "
            "source/context before the final request when present, and use simple "
            "delimiters instead of XML."
        ),
        clarify=(
            "Target model profile: Gemini/Antigravity. Use component-style bullets "
            "that separate objective, instruction, context, and output/verification "
            "format."
        ),
        behavior=(
            "Mitigation: keep long source/context in its own labeled block rather "
            "than interleaved — Gemini dilutes focus when context mixes with "
            "instructions. State the output format explicitly."
        ),
    ),
    "qwen": FamilyShape(
        family="qwen",
        rewrite=(
            "Target model profile: Qwen. Use direct, numbered Markdown and preserve exact "
            "file paths, flags, and literals when the user supplied them — Qwen follows literal instructions "
            "well but needs unambiguous references. Avoid discretionary phrasing."
        ),
        clarify=(
            "Target model profile: Qwen. Use concrete bullets naming exact paths, "
            "flags, and commands."
        ),
        behavior=(
            "Mitigation: Qwen tends to retry a failed shell command verbatim and, "
            "on repeated failure, delete needed files. State explicitly: 'Never "
            "repeat a failed command as-is — change a flag or inspect the error "
            "first.'"
        ),
    ),
    "deepseek": FamilyShape(
        family="deepseek",
        rewrite=(
            "Target model profile: DeepSeek. Use numbered deterministic steps; "
            "DeepSeek is a reasoning model and yields better output when visible "
            "sub-steps and final-answer contracts are explicit."
        ),
        clarify=(
            "Target model profile: DeepSeek. Number the visible steps and define the final answer."
        ),
        behavior=(
            "Mitigation: DeepSeek is a reasoning model — give it numbered "
            "deterministic steps, but do not request hidden chain-of-thought or "
            "over-constrain intermediate reasoning output."
        ),
    ),
    "glm": FamilyShape(
        family="glm",
        rewrite=(
            "Target model profile: GLM (Z.AI). Use numbered Markdown and state "
            "shell/environment needs inline and explicitly."
        ),
        clarify=("Target model profile: GLM (Z.AI). Use concrete numbered bullets."),
        behavior=(
            "Mitigation: GLM loses PATH and environment variables across shell "
            "calls. State explicitly: 'Persist PATH/env inline within each command; "
            "do not assume a prior export survives the next shell call.'"
        ),
    ),
    "minimax": FamilyShape(
        family="minimax",
        rewrite=(
            "Target model profile: MiniMax. Use agentic Markdown with an explicit "
            "definition of done and a required first artifact."
        ),
        clarify=(
            "Target model profile: MiniMax. Name the artifact to produce first; cap exploration."
        ),
        behavior=(
            "Mitigation: MiniMax enters an endless exploration loop and produces "
            "no artifact. State explicitly: 'Deliver a minimal first version "
            "immediately, then refine; cap exploration tool-calls before producing "
            "output.'"
        ),
    ),
    "kimi": FamilyShape(
        family="kimi",
        rewrite=(
            "Target model profile: Kimi. Use agentic Markdown; keep the task "
            "single-agent unless delegation is essential."
        ),
        clarify=(
            "Target model profile: Kimi. Keep bullets single-agent; avoid subagent delegation."
        ),
        behavior=(
            "Mitigation: under subagent delegation, Kimi forces its own model on "
            "ALL subagents and ignores their declared model, causing re-read loops. "
            "State explicitly: 'Do not delegate to subagents; if you must, set the "
            "subagent model explicitly.'"
        ),
    ),
    "mimo": FamilyShape(
        family="mimo",
        rewrite=(
            "Target model profile: MiMo. Use explicit numbered steps; avoid open-ended goals."
        ),
        clarify="Target model profile: MiMo. Number each step explicitly.",
        behavior=(
            "Mitigation: MiMo yields best results with structured sequential "
            "instructions — number every step and avoid open-ended discretion."
        ),
    ),
    "gemma": FamilyShape(
        family="gemma",
        rewrite=(
            "Target model profile: compact local model. Keep the output short, flat, "
            "and strongly labeled. Avoid nested structure and long explanations."
        ),
        clarify=("Target model profile: compact local model. Keep bullets short and concrete."),
        # No separate behavior: the compact-model constraints ARE the format guidance.
    ),
    "generic": FamilyShape(
        family="generic",
        rewrite="Target model profile: generic. Use clear, flat Markdown sections.",
        clarify="Target model profile: generic. Use concise action bullets.",
    ),
}
