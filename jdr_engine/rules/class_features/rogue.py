# jdr_engine/rules/class_features/rogue.py
"""Roublard — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from typing import Callable

from jdr_engine.dice import roll
from jdr_engine.dice.models import RollResult

# Progression Attaque sournoise (SRD 2014) — paliers par niveau
SNEAK_ATTACK_DICE_BY_LEVEL = (
    (1, 2, 1),
    (3, 4, 2),
    (5, 6, 3),
    (7, 8, 4),
    (9, 10, 5),
    (11, 12, 6),
    (13, 14, 7),
    (15, 16, 8),
    (17, 18, 9),
    (19, 20, 10),
)


def sneak_attack_dice_count(level: int) -> int:
    """Nombre de d6 Attaque sournoise pour un niveau donné."""
    for low, high, dice in SNEAK_ATTACK_DICE_BY_LEVEL:
        if low <= level <= high:
            return dice
    return 1


def sneak_attack_eligible(
    *,
    hit: bool,
    finesse_or_ranged: bool,
    has_advantage: bool,
    ally_within_5ft_of_target: bool,
    has_disadvantage: bool,
    already_used_this_turn: bool,
) -> bool:
    """
    Conditions exactes SRD 2014 Attaque sournoise (une fois par tour).

    - Toucher avec arme de finesse ou à distance
    - (Avantage sur le jet d'attaque) OU (allié à 1,5 m de la cible ET pas de désavantage)
    """
    if already_used_this_turn or not hit or not finesse_or_ranged:
        return False
    if has_advantage:
        return True
    return ally_within_5ft_of_target and not has_disadvantage


def roll_sneak_attack_damage(
    level: int,
    *,
    rng: Callable[[str], RollResult] | None = None,
) -> tuple[int, RollResult]:
    """Lance les d6 d'Attaque sournoise."""
    count = sneak_attack_dice_count(level)
    roller = rng or roll
    result = roller(f"{count}d6")
    return result.total, result
