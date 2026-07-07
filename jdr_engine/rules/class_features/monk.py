# jdr_engine/rules/class_features/monk.py
"""Moine — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from typing import Any

from jdr_engine.rules.class_features.common import feature_state

MARTIAL_ARTS_DIE_BY_LEVEL = (
    (1, 4, 4),
    (5, 10, 6),
    (11, 16, 8),
    (17, 20, 10),
)

KI_OPTIONS_LEVEL_2 = frozenset({
    "flurry_of_blows",
    "patient_defense",
    "step_of_the_wind",
})

KI_OPTION_COSTS = {
    "flurry_of_blows": 1,
    "patient_defense": 1,
    "step_of_the_wind": 1,
}


def martial_arts_die(level: int) -> int:
    """Dé d'arts martiaux (faces) selon niveau SRD 2014."""
    for low, high, faces in MARTIAL_ARTS_DIE_BY_LEVEL:
        if low <= level <= high:
            return faces
    return 4


def ki_points_max(level: int) -> int:
    """Points de Ki = niveau de moine (SRD 2014, niv. 2+)."""
    return level if level >= 2 else 0


def ki_max(level: int) -> int:
    """Alias — pool Ki selon le niveau."""
    return ki_points_max(level)


def ki_points_remaining(choices: dict[str, Any], *, level: int) -> int:
    maximum = ki_points_max(level)
    if maximum == 0:
        return 0
    state = feature_state(choices)
    if "ki_points_remaining" not in state:
        return maximum
    return max(0, min(int(state["ki_points_remaining"]), maximum))


def init_ki_points(choices: dict[str, Any], *, level: int) -> dict[str, Any]:
    """Initialise ou synchronise le compteur Ki (création / montée de niveau)."""
    maximum = ki_points_max(level)
    if maximum == 0:
        return choices
    state = feature_state(choices)
    if "ki_points_remaining" not in state:
        state["ki_points_remaining"] = maximum
    else:
        state["ki_points_remaining"] = min(
            int(state["ki_points_remaining"]), maximum
        )
    return {**choices, "feature_state": state}


def reset_ki_points(choices: dict[str, Any], *, level: int) -> dict[str, Any]:
    """Repos court ou long — recharge complète du Ki (SRD 2014)."""
    maximum = ki_points_max(level)
    if maximum == 0:
        return choices
    state = feature_state(choices)
    state["ki_points_remaining"] = maximum
    return {**choices, "feature_state": state}


def spend_ki_points(
    choices: dict[str, Any],
    amount: int,
    *,
    level: int,
) -> dict[str, Any]:
    remaining = ki_points_remaining(choices, level=level)
    if amount > remaining:
        raise ValueError("Points de Ki insuffisants.")
    state = feature_state(choices)
    state["ki_points_remaining"] = remaining - amount
    return {**choices, "feature_state": state}


def unarmored_movement_bonus(level: int) -> int:
    """Bonus vitesse sans armure (niv. 2+) : +10 ft."""
    return 10 if level >= 2 else 0


def ki_options(level: int) -> frozenset[str]:
    """Options Ki disponibles (niv. 2+)."""
    if level < 2:
        return frozenset()
    return KI_OPTIONS_LEVEL_2


def deflect_missiles_can_throw(level: int, damage_reduced_to_zero: bool, ki_remaining: int) -> bool:
    """
    Dévier les projectiles (niv. 3) : lancer en retour si dégâts réduits à 0 et 1 Ki.
    """
    return level >= 3 and damage_reduced_to_zero and ki_remaining >= 1
