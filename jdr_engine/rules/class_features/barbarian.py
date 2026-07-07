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


def rage_uses_max(level: int) -> int:
    """Utilisations de Rage par repos long (SRD 2014)."""
    return 3 if level >= 3 else 2


def rage_uses_remaining(choices: dict[str, Any], *, level: int) -> int:
    state = feature_state(choices)
    if "rage_uses_remaining" not in state:
        return rage_uses_max(level)
    return max(0, int(state["rage_uses_remaining"]))


def init_rage_uses(choices: dict[str, Any], *, level: int) -> dict[str, Any]:
    """Initialise le compteur de Rage (création / montée de niveau)."""
    state = feature_state(choices)
    state.setdefault("rage_uses_remaining", rage_uses_max(level))
    return {**choices, "feature_state": state}


def reset_rage_uses_on_long_rest(choices: dict[str, Any], *, level: int) -> dict[str, Any]:
    state = feature_state(choices)
    state["rage_uses_remaining"] = rage_uses_max(level)
    return {**choices, "feature_state": state}


def can_start_rage(choices: dict[str, Any], *, level: int) -> bool:
    return rage_uses_remaining(choices, level=level) > 0 and not rage_active(choices)


def rage_active(choices: dict[str, Any]) -> bool:
    return bool(feature_state(choices).get("rage_active"))


def start_rage(choices: dict[str, Any], *, level: int) -> dict[str, Any]:
    remaining = rage_uses_remaining(choices, level=level)
    if remaining <= 0:
        raise ValueError("Aucune utilisation de Rage restante.")
    state = feature_state(choices)
    state["rage_uses_remaining"] = remaining - 1
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


def totem_bear_resistances_active(
    character_choices: dict[str, Any],
    *,
    rage_is_active: bool,
) -> bool:
    """Esprit de l'ours : résistance (sauf psychique) pendant la Rage."""
    if not rage_is_active:
        return False
    return (
        character_choices.get("specialization") == "totem_warrior"
        and character_choices.get("totem_spirit") == "bear"
    )


def effective_rage_resistances(
    character_choices: dict[str, Any],
    *,
    level: int,
    rage_is_active: bool,
) -> frozenset[str]:
    """Résistances en Rage — base barbare + ours totémique si applicable."""
    if not rage_is_active:
        return frozenset()
    if totem_bear_resistances_active(character_choices, rage_is_active=True):
        return frozenset({"all_except_psychic"})
    return rage_resistances()
