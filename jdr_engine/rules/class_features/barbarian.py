# jdr_engine/rules/class_features/barbarian.py
"""Barbare — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from typing import Any

from jdr_engine.rules.class_features.common import feature_state

RAGE_DAMAGE_BONUS_BY_LEVEL = (
    (1, 8, 2),
    (9, 15, 3),
    (16, 20, 4),
)

RAGE_END_TRIGGERS = (
    "no_attack_or_damage_since_last_turn",
    "unconscious",
    "end_bonus_action",
)


def rage_damage_bonus(level: int) -> int:
    """Bonus dégâts mêlée FOR en Rage (SRD 2014)."""
    for low, high, bonus in RAGE_DAMAGE_BONUS_BY_LEVEL:
        if low <= level <= high:
            return bonus
    return 2


def rage_resistances() -> frozenset[str]:
    """Résistances actives en Rage : contondant, perforant, tranchant."""
    return frozenset({"bludgeoning", "piercing", "slashing"})


def rage_end_triggers() -> tuple[str, ...]:
    """Conditions de fin de Rage (SRD 2014)."""
    return RAGE_END_TRIGGERS


def rage_active(choices: dict[str, Any]) -> bool:
    return bool(feature_state(choices).get("rage_active"))


def start_rage(choices: dict[str, Any]) -> dict[str, Any]:
    state = feature_state(choices)
    state["rage_active"] = True
    state["reckless_active"] = False
    return {**choices, "feature_state": state}


def end_rage(choices: dict[str, Any]) -> dict[str, Any]:
    state = feature_state(choices)
    state["rage_active"] = False
    state["reckless_active"] = False
    return {**choices, "feature_state": state}


def reckless_active(choices: dict[str, Any]) -> bool:
    return bool(feature_state(choices).get("reckless_active"))


def activate_reckless_attack(choices: dict[str, Any]) -> dict[str, Any]:
    state = feature_state(choices)
    state["reckless_active"] = True
    return {**choices, "feature_state": state}


def deactivate_reckless_attack(choices: dict[str, Any]) -> dict[str, Any]:
    state = feature_state(choices)
    state["reckless_active"] = False
    return {**choices, "feature_state": state}
