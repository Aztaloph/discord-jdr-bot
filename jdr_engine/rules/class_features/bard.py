# jdr_engine/rules/class_features/bard.py
"""Barde — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import ability_modifier
from jdr_engine.rules.class_features.common import feature_state, set_feature_state

BARDIC_INSPIRATION_DIE_BY_LEVEL: dict[int, int] = {1: 6, 2: 6, 3: 6}
SONG_OF_REST_DIE_BY_LEVEL: dict[int, int] = {2: 6, 3: 6}


def bardic_inspiration_uses_max(cha_score: int) -> int:
    return max(1, ability_modifier(cha_score))


def bardic_inspiration_die(level: int) -> int:
    return BARDIC_INSPIRATION_DIE_BY_LEVEL.get(level, 6)


def bardic_inspiration_remaining(choices: dict, *, cha_score: int) -> int:
    state = feature_state(choices)
    if "bardic_inspiration_remaining" not in state:
        return bardic_inspiration_uses_max(cha_score)
    return max(0, int(state["bardic_inspiration_remaining"]))


def song_of_rest_die(level: int) -> int:
    return SONG_OF_REST_DIE_BY_LEVEL.get(level, 0)


def init_bard_features(
    choices: dict,
    *,
    level: int,
    cha_score: int,
) -> dict:
    state = feature_state(choices)
    state.setdefault(
        "bardic_inspiration_remaining",
        bardic_inspiration_uses_max(cha_score),
    )
    return set_feature_state(choices, state)


def reset_bardic_inspiration_on_long_rest(
    choices: dict,
    *,
    cha_score: int,
) -> dict:
    state = feature_state(choices)
    state["bardic_inspiration_remaining"] = bardic_inspiration_uses_max(cha_score)
    return set_feature_state(choices, state)


def spend_bardic_inspiration(choices: dict, *, cha_score: int) -> dict:
    remaining = bardic_inspiration_remaining(choices, cha_score=cha_score)
    if remaining <= 0:
        raise ValueError("Aucune Inspiration bardique restante.")
    state = feature_state(choices)
    state["bardic_inspiration_remaining"] = remaining - 1
    return set_feature_state(choices, state)
