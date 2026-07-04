"""Hard-prompt classification for cloud escalation."""

from __future__ import annotations

import os

from prompt_improve.shared.config import _HARD_DOMAIN_SIGNALS, _HARD_INTENT_SIGNALS, TASK_VERBS_RE


def needs_cloud_intelligence(prompt: str, mode: str) -> bool:
    """Decide whether the local model is likely insufficient and the prompt should
    escalate to a frontier-class CLOUD model. Conservative: escalate only on clear
    domain/intent complexity signals. Disable with OLLAMA_IMPROVE_CLOUD_INTELLIGENCE=0."""
    if os.environ.get("OLLAMA_IMPROVE_CLOUD_INTELLIGENCE", "1") == "0":
        return False
    if len(prompt) >= 40 and _HARD_DOMAIN_SIGNALS.search(prompt):
        return True
    if len(prompt) > 80 and _HARD_INTENT_SIGNALS.search(prompt):
        return True
    if mode == "clarify" and len(prompt) > 500 and len(TASK_VERBS_RE.findall(prompt)) >= 3:
        return True
    return False
