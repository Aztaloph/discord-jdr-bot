# jdr_engine/rules/class_features/fighter.py
"""Guerrier — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from typing import Any, Callable

from jdr_engine.dice import roll
from jdr_engine.dice.models import RollResult

from jdr_engine.rules.class_features.common import feature_state

SRD_FIGHTING_STYLES = frozenset({
    "archery",
    "defense",
    "dueling",
    "great_weapon_fighting",
    "protection",
    "two_weapon_fighting",
})


def roll_second_wind_healing(
    level: int,
    *,
    rng: Callable[[str], RollResult] | None = None,
) -> tuple[int, RollResult]:
    """
    Second Souffle (SRD 2014) : regagne 1d10 + niveau de guerrier.

    Action bonus ; une fois entre deux repos (court ou long).
    """
    if level < 1:
        raise ValueError("level must be >= 1")
    roller = rng or roll
    result = roller(f"1d10+{level}")
    return result.total, result


def second_wind_available(choices: dict[str, Any]) -> bool:
    state = feature_state(choices)
    return not state.get("second_wind_used", False)


def use_second_wind(choices: dict[str, Any]) -> dict[str, Any]:
    state = feature_state(choices)
    state["second_wind_used"] = True
    return {**choices, "feature_state": state}


def reset_short_rest_features(choices: dict[str, Any]) -> dict[str, Any]:
    """Repos court SRD : Second Wind + Action Surge."""
    state = feature_state(choices)
    state["second_wind_used"] = False
    state["action_surge_used"] = False
    return {**choices, "feature_state": state}


def action_surge_available(choices: dict[str, Any]) -> bool:
    state = feature_state(choices)
    return not state.get("action_surge_used", False)


def use_action_surge(choices: dict[str, Any]) -> dict[str, Any]:
    state = feature_state(choices)
    state["action_surge_used"] = True
    return {**choices, "feature_state": state}
