# jdr_engine/rules/class_features/common.py
"""Utilitaires communs features de classe."""
from __future__ import annotations

from typing import Any


def feature_state(choices: dict[str, Any]) -> dict[str, Any]:
    """État runtime des features (rage, repos, etc.)."""
    raw = choices.get("feature_state")
    return dict(raw) if isinstance(raw, dict) else {}


def set_feature_state(choices: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    updated = dict(choices)
    updated["feature_state"] = state
    return updated
