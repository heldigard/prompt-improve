"""Target-awareness package: detect the target CLI/model, then shape the
improved prompt for that family (format + behavior).

Public API (stable import surface — `rules.py` and `improve.py` import from here):

- :class:`TargetProfile`, :data:`GENERIC_TARGET` — the classified target
- :func:`target_profile_from_request` — entry point: payload + env -> profile
- :func:`profile_for_model` — classify a model string
- :func:`target_guidance` — per-family prompt-shape guidance (format + behavior)

Internal layout (vertical slice by responsibility):

- :mod:`.profile` — the HOW (detection / classification logic)
- :mod:`.shape`   — the WHAT (per-family format + behavior registry)
"""

from __future__ import annotations

from prompt_improve.features.target.profile import (
    GENERIC_TARGET,
    TargetProfile,
    profile_for_cli,
    profile_for_model,
    target_profile_from_request,
)
from prompt_improve.features.target.shape import target_guidance

__all__ = [
    "GENERIC_TARGET",
    "TargetProfile",
    "profile_for_cli",
    "profile_for_model",
    "target_guidance",
    "target_profile_from_request",
]
