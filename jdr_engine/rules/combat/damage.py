# jdr_engine/rules/combat/damage.py
"""
Application des dégâts en combat — lot C3a.

Le critique **double les dés** de la notation, pas le modificateur fixe (SRD 5.1).
Ex. ``1d8+3`` en critique → ``2d8+3``.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from jdr_engine.dice.parser import parse

RandInt = Callable[[int, int], int]


@dataclass(frozen=True)
class DamageRollResult:
    """Résultat d'un jet de dégâts."""

    dice_notation: str
    rolls: tuple[int, ...]
    modifier: int
    total: int
    critical: bool


@dataclass(frozen=True)
class DamageApplicationResult:
    """PV avant/après application — fonction pure."""

    hp_before: int
    hp_after: int
    damage_dealt: int


def _default_randint(a: int, b: int) -> int:
    return random.randint(a, b)


def roll_damage(
    dice_notation: str,
    *,
    critical: bool = False,
    rng: RandInt | None = None,
) -> DamageRollResult:
    """
    Lance les dés de dégâts.

    En critique, le **nombre de dés** est doublé ; le modificateur fixe est inchangé.
    """
    count, faces, modifier, _sign = parse(dice_notation)
    dice_count = count * 2 if critical else count
    randint = rng or _default_randint
    rolls = tuple(randint(1, faces) for _ in range(dice_count))
    total = sum(rolls) + modifier
    label = dice_notation
    if critical:
        label = f"{dice_count}d{faces}{'+' if modifier >= 0 else ''}{modifier if modifier else ''}"
    return DamageRollResult(
        dice_notation=label,
        rolls=rolls,
        modifier=modifier,
        total=total,
        critical=critical,
    )


def apply_damage_to_hp(hp_current: int, amount: int) -> DamageApplicationResult:
    """
    Applique des dégâts avec plancher à 0 PV.

    ``damage_dealt`` reflète la perte réelle (différence avant/après).
    """
    if amount < 0:
        raise ValueError("Les dégâts ne peuvent pas être négatifs.")
    hp_after = max(0, hp_current - amount)
    return DamageApplicationResult(
        hp_before=hp_current,
        hp_after=hp_after,
        damage_dealt=hp_current - hp_after,
    )
