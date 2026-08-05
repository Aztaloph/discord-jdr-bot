# jdr_engine/rules/combat/buffs/hunters_mark.py
"""Marque du chasseur — bonus +1d6 dégâts (lot B4, SRD 2014 simplifié)."""
from __future__ import annotations

import random
from typing import Callable

from jdr_engine.domain.combat.combatant import Combatant

RandInt = Callable[[int, int], int]


def _default_randint(a: int, b: int) -> int:
    return random.randint(a, b)


def hunters_mark_bonus_applies(
    target: Combatant,
    source_id: str | None,
) -> bool:
    """Vrai si la cible est marquée par ``source_id`` (combatant lanceur)."""
    return (
        source_id is not None
        and target.hunters_mark_caster_id is not None
        and target.hunters_mark_caster_id == source_id
    )


def roll_hunters_mark_bonus(*, rng: RandInt | None = None) -> int:
    """Lance le +1d6 de la marque du chasseur."""
    randint = rng or _default_randint
    return randint(1, 6)
