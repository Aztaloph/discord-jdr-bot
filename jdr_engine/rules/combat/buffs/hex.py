# jdr_engine/rules/combat/buffs/hex.py
"""Maléfice — bonus +1d6 dégâts de sort (lot B4e, SRD 2014 simplifié)."""
from __future__ import annotations

import random
from typing import Callable

from jdr_engine.domain.combat.active_effect import ActiveEffect

RandInt = Callable[[int, int], int]


def _default_randint(a: int, b: int) -> int:
    return random.randint(a, b)


def hex_bonus_applies(
    target_effects: tuple[ActiveEffect, ...],
    source_id: str | None,
) -> bool:
    """Vrai si la cible porte un maléfice posé par ``source_id``."""
    if source_id is None:
        return False
    return any(
        effect.effect_id == "hexed" and effect.source_id == source_id
        for effect in target_effects
    )


def roll_hex_bonus(*, rng: RandInt | None = None) -> int:
    """Lance le +1d6 nécrotique du maléfice."""
    randint = rng or _default_randint
    return randint(1, 6)
