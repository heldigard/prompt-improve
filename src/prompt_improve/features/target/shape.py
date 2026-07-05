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
            "agent runs (test, grep, or LSP refs)."
        ),
    ),
    "openai-gpt": FamilyShape(
        family="openai-gpt",
        rewrite=(
            "Target model profile: OpenAI GPT/Codex. Output clean Markdown sections "
            "with explicit role/workflow guidance, concrete tool-use or verification "
            "steps when inferable, and backticks around file paths/functions/classes. "
            "Separate instructions from the user's original input; do not use XML."
        ),
        clarify=(
            "Target model profile: OpenAI GPT/Codex. Use 1-3 Markdown bullets that "
            "name concrete actions, verification, and any TODO/planning need. Use "
            "backticks for paths/functions/classes. Do not use XML."
        ),
        behavior=(
            "Mitigation: structure the spec as FILES / SIGNATURE / STEPS / EDGE "
            "CASES / ACCEPTANCE — GPT/Codex yields measurably better output from an "
            "explicit deterministic spec than from open prose."
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
            "Target model profile: Qwen. Use direct, numbered Markdown with exact "
            "file paths, flags, and literals — Qwen follows literal instructions "
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
            "DeepSeek is a reasoning model and yields better output when sub-steps "
            "are explicit and chain-of-thought is not over-constrained."
        ),
        clarify=(
            "Target model profile: DeepSeek. Number the steps; let the model reason between them."
        ),
        behavior=(
            "Mitigation: DeepSeek is a reasoning model — give it numbered "
            "deterministic steps and leave room for chain-of-thought; do not "
            "over-constrain intermediate output."
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
