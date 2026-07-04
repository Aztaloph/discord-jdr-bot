# jdr_engine/rules/character_creation/rolling.py
"""Tirage 4d6 garder 3 — SRD 2014."""
from __future__ import annotations

import random
from typing import Callable

RandInt = Callable[[int, int], int]


def _default_randint(a: int, b: int) -> int:
    return random.randint(a, b)


def roll_4d6_drop_lowest(*, rng: RandInt | None = None) -> tuple[int, list[int]]:
    """Lance 4d6, retire le plus bas, retourne (total, les 4 valeurs)."""
    rand = rng or _default_randint
    rolls = [rand(1, 6) for _ in range(4)]
    kept = sorted(rolls)[1:]
    return sum(kept), rolls


def roll_ability_score_pool(*, rng: RandInt | None = None) -> list[int]:
    """Six scores à assigner aux caractéristiques."""
    return [roll_4d6_drop_lowest(rng=rng)[0] for _ in range(6)]
