"""prompt-improve CLI for offline prompt testing + ops inspection.

Mirrors the ergonomics of `skill-router`: a thin argparse surface over the
hook internals so you can verify modes, classify behavior, and replay a prompt
without going through a UserPromptSubmit roundtrip.

Subcommands:
  improve    — run the full pipeline against one prompt (mirrors the hook).
  classify   — hard-prompt escalation decision (cloud-first?).
  detect     — trivial / concrete-target / anaphoric classification.
  target     — show the resolved target profile (cli/model family).
  version    — print version, exit 0.

Usage:
  python3 -m prompt_improve.cli improve --prompt "fix foo.py"
  python3 -m prompt_improve.cli detect --prompt "fix foo.py"
  python3 -m prompt_improve.cli target
"""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_improve(args: argparse.Namespace) -> int:
    """Replay one prompt through the full improve pipeline.

    Mirrors what the hook does in additionalContext mode, but prints to stdout
    so the user can audit the rewrite output before the controller sees it.
    """
    from prompt_improve.features.detect import (
        decide_mode,
        depends_on_conversation_context,
        detect_trivial,
        has_concrete_target,
    )
    from prompt_improve.features.improve import route_and_improve
    from prompt_improve.features.rules import rule_based_suggestions
    from prompt_improve.features.target import target_profile_from_request
    from prompt_improve.shared import metrics

    prompt = args.prompt
    cwd = args.cwd
    data: dict | None = {"prompt": prompt, "cwd": cwd} if cwd else {"prompt": prompt}

    if detect_trivial(prompt):
        print(json.dumps({"status": "trivial", "prompt": prompt}, ensure_ascii=False))
        return 0
    if depends_on_conversation_context(prompt) or has_concrete_target(prompt):
        print(
            json.dumps(
                {"status": "passthrough", "reason": "concrete/anaphoric"},
                ensure_ascii=False,
            )
        )
        return 0

    mode = args.mode or decide_mode(prompt)
    target = target_profile_from_request(data)
    result = route_and_improve(prompt, mode, cwd, target)
    if not result:
        fallback = rule_based_suggestions(prompt)
        print(
            json.dumps(
                {
                    "status": "fallback",
                    "source": "rules",
                    "mode": mode,
                    "improved": fallback,
                },
                ensure_ascii=False,
            )
        )
        return 0

    improved, source = result
    print(
        json.dumps(
            {"status": "improved", "source": source, "mode": mode, "improved": improved},
            ensure_ascii=False,
        )
    )
    metrics.emit()
    return 0


def _cmd_classify(args: argparse.Namespace) -> int:
    from prompt_improve.features.classify import needs_cloud_intelligence

    decision = needs_cloud_intelligence(args.prompt, args.mode)
    print(json.dumps({"cloud_intelligence": decision, "mode": args.mode}, ensure_ascii=False))
    return 0


def _cmd_detect(args: argparse.Namespace) -> int:
    from prompt_improve.features.detect import (
        decide_mode,
        depends_on_conversation_context,
        detect_language,
        detect_trivial,
        has_concrete_target,
    )

    out = {
        "language": detect_language(args.prompt),
        "trivial": detect_trivial(args.prompt),
        "concrete_target": has_concrete_target(args.prompt),
        "anaphoric": depends_on_conversation_context(args.prompt),
        "mode": decide_mode(args.prompt),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


def _cmd_target(args: argparse.Namespace) -> int:
    from prompt_improve.features.target import target_profile_from_request

    profile = target_profile_from_request()
    print(json.dumps(profile, default=lambda o: getattr(o, "__dict__", str(o)), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="prompt-improve", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    from prompt_improve import __version__

    p.add_argument("--version", action="version", version=f"prompt-improve {__version__}")

    pi = sub.add_parser("improve", help="run the full hook pipeline against one prompt")
    pi.add_argument("--prompt", required=True)
    pi.add_argument("--mode", choices=("rewrite", "clarify"), help="override OLLAMA_IMPROVE_MODE")
    pi.add_argument("--cwd", help="project cwd for hint resolution")
    pi.set_defaults(func=_cmd_improve)

    pc = sub.add_parser("classify", help="cloud-intelligence decision for one prompt")
    pc.add_argument("--prompt", required=True)
    pc.add_argument("--mode", choices=("rewrite", "clarify"), default="rewrite")
    pc.set_defaults(func=_cmd_classify)

    pd = sub.add_parser("detect", help="trivial/concrete/anaphoric/mode classification")
    pd.add_argument("--prompt", required=True)
    pd.set_defaults(func=_cmd_detect)

    pt = sub.add_parser("target", help="resolved target profile (CLI / model family)")
    pt.set_defaults(func=_cmd_target)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
