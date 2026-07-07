# jdr_engine/rules/class_features/wizard.py
"""Magicien — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

import math

from jdr_engine.rules.class_features.common import feature_state, set_feature_state


def arcane_recovery_pool(level: int) -> int:
    """Somme max des niveaux d'emplacements récupérables (moitié niveau mage, arr. sup.)."""
    return max(1, math.ceil(level / 2))


def arcane_recovery_max_slot_level(level: int) -> int:
    """Aucun emplacement niv. 6+ (SRD) — au niv. 1-3, plafond = niveau de mage."""
    return min(level, 5)


def arcane_recovery_available(choices: dict) -> bool:
    state = feature_state(choices)
    return not bool(state.get("arcane_recovery_used"))


def init_wizard_features(choices: dict, *, level: int) -> dict:
    state = feature_state(choices)
    if level >= 1:
        state.setdefault("arcane_recovery_used", False)
    return set_feature_state(choices, state)


def reset_arcane_recovery_on_long_rest(choices: dict) -> dict:
    state = feature_state(choices)
    state["arcane_recovery_used"] = False
    return set_feature_state(choices, state)


def apply_arcane_recovery(
    choices: dict,
    *,
    level: int,
    slots_used: dict[int, int],
) -> tuple[dict, dict[int, int], int]:
    """
    Récupère des emplacements lors d'un repos court (1/jour).

    Returns:
        (choices mis à jour, slots_used mis à jour, niveaux récupérés)
    """
    if not arcane_recovery_available(choices):
        raise ValueError("Récupération arcanique déjà utilisée (repos long requis).")

    pool = arcane_recovery_pool(level)
    max_slot = arcane_recovery_max_slot_level(level)
    recovered = 0
    used = dict(slots_used)

    for slot_level in sorted(used.keys()):
        if recovered >= pool:
            break
        if slot_level > max_slot:
            continue
        while used.get(slot_level, 0) > 0 and recovered + slot_level <= pool:
            used[slot_level] -= 1
            recovered += slot_level

    state = feature_state(choices)
    state["arcane_recovery_used"] = True
    return set_feature_state(choices, state), used, recovered
