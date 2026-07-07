# jdr_engine/rules/class_features/cleric.py
"""Clerc — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from jdr_engine.rules.class_features.common import feature_state, set_feature_state

CHANNEL_DIVINITY_USES_BY_LEVEL: dict[int, int] = {2: 1, 3: 1}


def channel_divinity_uses_max(level: int) -> int:
    return CHANNEL_DIVINITY_USES_BY_LEVEL.get(level, 0)


def channel_divinity_remaining(choices: dict, *, level: int) -> int:
    state = feature_state(choices)
    maximum = channel_divinity_uses_max(level)
    if maximum <= 0:
        return 0
    if "channel_divinity_remaining" not in state:
        return maximum
    return max(0, int(state["channel_divinity_remaining"]))


def preserve_life_pool(level: int) -> int:
    """Préservation de la vie — 5 × niveau de clerc (SRD 2014)."""
    return 5 * level


def preserve_life_remaining(choices: dict, *, level: int) -> int:
    state = feature_state(choices)
    maximum = preserve_life_pool(level)
    if "preserve_life_remaining" not in state:
        return maximum
    return max(0, min(int(state["preserve_life_remaining"]), maximum))


def disciple_of_life_bonus(spell_level: int) -> int:
    """Disciple de la vie : +2 + niveau du sort soigné."""
    return 2 + max(0, spell_level)


def init_cleric_features(choices: dict, *, level: int) -> dict:
    state = feature_state(choices)
    if level >= 2:
        state.setdefault(
            "channel_divinity_remaining",
            channel_divinity_uses_max(level),
        )
        state.setdefault(
            "preserve_life_remaining",
            preserve_life_pool(level),
        )
    return set_feature_state(choices, state)


def reset_channel_divinity_on_short_rest(choices: dict, *, level: int) -> dict:
    state = feature_state(choices)
    maximum = channel_divinity_uses_max(level)
    if maximum > 0:
        state["channel_divinity_remaining"] = maximum
    return set_feature_state(choices, state)


def reset_preserve_life_on_long_rest(choices: dict, *, level: int) -> dict:
    state = feature_state(choices)
    if level >= 2:
        state["preserve_life_remaining"] = preserve_life_pool(level)
    return set_feature_state(choices, state)


def spend_preserve_life(choices: dict, *, level: int, amount: int) -> dict:
    if amount <= 0:
        raise ValueError("Montant de soin invalide.")
    remaining = preserve_life_remaining(choices, level=level)
    if amount > remaining:
        raise ValueError(f"Réserve Préservation de la vie insuffisante ({remaining} PV).")
    state = feature_state(choices)
    state["preserve_life_remaining"] = remaining - amount
    return set_feature_state(choices, state)


def refresh_preserve_life_on_level_up(
    choices: dict,
    *,
    old_level: int,
    new_level: int,
) -> dict:
    if new_level <= old_level or new_level < 2:
        return choices
    state = feature_state(choices)
    state["preserve_life_remaining"] = preserve_life_pool(new_level)
    return set_feature_state(choices, state)


def collect_bonus_armor_proficiencies(domain_id: str | None) -> tuple[str, ...]:
    if domain_id == "life":
        return ("heavy",)
    return ()
