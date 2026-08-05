# jdr_engine/rules/combat/buffs/hunters_mark.py
"""Marque du chasseur — bonus +1d6 dégâts (lot B4, SRD 2014 simplifié)."""
from __future__ import annotations

import random
from typing import Callable

from jdr_engine.domain.combat.active_effect import ActiveEffect

RandInt = Callable[[int, int], int]


def _default_randint(a: int, b: int) -> int:
    return random.randint(a, b)


def hunters_mark_bonus_applies(
    target_effects: tuple[ActiveEffect, ...],
    source_id: str | None,
) -> bool:
    """Vrai si la cible porte une marque posée par ``source_id``."""
    if source_id is None:
        return False
    return any(
        effect.effect_id == "hunters_mark" and effect.source_id == source_id
        for effect in target_effects
    )


def roll_hunters_mark_bonus(*, rng: RandInt | None = None) -> int:
    """Lance le +1d6 de la marque du chasseur."""
    randint = rng or _default_randint
    return randint(1, 6)
