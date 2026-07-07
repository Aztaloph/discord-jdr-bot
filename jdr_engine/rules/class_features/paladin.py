# jdr_engine/rules/class_features/paladin.py
"""Paladin — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from typing import Any

from jdr_engine.domain.character.ability_scores import ability_modifier
from jdr_engine.rules.class_features.common import feature_state, set_feature_state
from jdr_engine.rules.spellcasting.state import consume_spell_slot
from jdr_engine.domain.character.character import Character


def divine_sense_uses_max(cha_score: int) -> int:
    """1 + modificateur de Charisme (minimum 1 utilisation)."""
    mod = ability_modifier(cha_score)
    return max(1, 1 + mod)


def divine_sense_remaining(choices: dict[str, Any], *, cha_score: int) -> int:
    state = feature_state(choices)
    if "divine_sense_remaining" not in state:
        return divine_sense_uses_max(cha_score)
    return max(0, int(state["divine_sense_remaining"]))


def lay_on_hands_pool_max(level: int) -> int:
    return 5 * level


def lay_on_hands_remaining(choices: dict[str, Any], *, level: int) -> int:
    state = feature_state(choices)
    maximum = lay_on_hands_pool_max(level)
    if "lay_on_hands_remaining" not in state:
        return maximum
    return max(0, min(int(state["lay_on_hands_remaining"]), maximum))


def channel_divinity_uses_max(level: int) -> int:
    return 1 if level >= 3 else 0


def channel_divinity_remaining(choices: dict[str, Any], *, level: int) -> int:
    state = feature_state(choices)
    maximum = channel_divinity_uses_max(level)
    if maximum <= 0:
        return 0
    if "channel_divinity_remaining" not in state:
        return maximum
    return max(0, int(state["channel_divinity_remaining"]))


def init_paladin_features(
    choices: dict[str, Any],
    *,
    level: int,
    cha_score: int,
) -> dict[str, Any]:
    state = feature_state(choices)
    state.setdefault("divine_sense_remaining", divine_sense_uses_max(cha_score))
    state.setdefault("lay_on_hands_remaining", lay_on_hands_pool_max(level))
    if level >= 3:
        state.setdefault(
            "channel_divinity_remaining",
            channel_divinity_uses_max(level),
        )
    return set_feature_state(choices, state)


def refresh_lay_on_hands_on_level_up(
    choices: dict[str, Any],
    *,
    old_level: int,
    new_level: int,
) -> dict[str, Any]:
    state = feature_state(choices)
    old_max = lay_on_hands_pool_max(old_level)
    new_max = lay_on_hands_pool_max(new_level)
    current = int(state.get("lay_on_hands_remaining", old_max))
    state["lay_on_hands_remaining"] = min(new_max, current + (new_max - old_max))
    if new_level >= 3 and "channel_divinity_remaining" not in state:
        state["channel_divinity_remaining"] = channel_divinity_uses_max(new_level)
    return set_feature_state(choices, state)


def reset_divine_sense_on_long_rest(
    choices: dict[str, Any],
    *,
    cha_score: int,
) -> dict[str, Any]:
    state = feature_state(choices)
    state["divine_sense_remaining"] = divine_sense_uses_max(cha_score)
    return set_feature_state(choices, state)


def reset_lay_on_hands_on_long_rest(
    choices: dict[str, Any],
    *,
    level: int,
) -> dict[str, Any]:
    state = feature_state(choices)
    state["lay_on_hands_remaining"] = lay_on_hands_pool_max(level)
    return set_feature_state(choices, state)


def reset_channel_divinity_on_short_rest(
    choices: dict[str, Any],
    *,
    level: int,
) -> dict[str, Any]:
    state = feature_state(choices)
    maximum = channel_divinity_uses_max(level)
    if maximum > 0:
        state["channel_divinity_remaining"] = maximum
    return set_feature_state(choices, state)


def spend_lay_on_hands(
    choices: dict[str, Any],
    *,
    level: int,
    amount: int,
) -> dict[str, Any]:
    if amount <= 0:
        raise ValueError("Montant de soin invalide.")
    remaining = lay_on_hands_remaining(choices, level=level)
    if amount > remaining:
        raise ValueError(
            f"Réserve insuffisante ({remaining} PV restants sur {lay_on_hands_pool_max(level)})."
        )
    state = feature_state(choices)
    state["lay_on_hands_remaining"] = remaining - amount
    return set_feature_state(choices, state)


def spend_divine_sense(choices: dict[str, Any], *, cha_score: int) -> dict[str, Any]:
    remaining = divine_sense_remaining(choices, cha_score=cha_score)
    if remaining <= 0:
        raise ValueError("Aucune utilisation de Sens divin restante.")
    state = feature_state(choices)
    state["divine_sense_remaining"] = remaining - 1
    return set_feature_state(choices, state)


def divine_smite_damage_dice(slot_level: int) -> tuple[int, int]:
    """Retourne (nombre de d8, faces=8) pour Châtiment divin SRD 2014."""
    if slot_level < 1:
        raise ValueError("Emplacement niv. 1+ requis pour Châtiment divin.")
    dice = min(5, 2 + max(0, slot_level - 1))
    return dice, 8


def apply_divine_smite(
    character: Character,
    *,
    slot_level: int = 1,
) -> Character:
    """Consomme un emplacement pour Châtiment divin (dégâts calculés séparément)."""
    dice, _ = divine_smite_damage_dice(slot_level)
    updated = consume_spell_slot(character, slot_level)
    return updated
