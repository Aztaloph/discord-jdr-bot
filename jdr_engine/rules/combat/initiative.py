# jdr_engine/rules/combat/initiative.py
"""
Initiative SRD 5.1 2014 — jet 1d20 + modificateur DEX, ordre figé (lot C2).

Départage des égalités (ADR-004 § décision 8) :
    1. total d'initiative décroissant ;
    2. à égalité, ``combatant_id`` croissant (ordre lexicographique).

Le critère 2 est indépendant de l'ordre d'insertion ou du tri Python.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from jdr_engine.rules.derived_stats import calculate_initiative


@dataclass(frozen=True)
class InitiativeRollResult:
    """Résultat de jet pour un combattant."""

    combatant_id: str
    d20: int
    modifier: int

    @property
    def total(self) -> int:
        return self.d20 + self.modifier


def roll_initiative(
    combatant_id: str,
    dex_modifier: int,
    *,
    rng: Callable[[], int] | None = None,
) -> InitiativeRollResult:
    """Lance 1d20 + modificateur DEX pour un combattant."""
    roll_fn = rng or (lambda: random.randint(1, 20))
    modifier = calculate_initiative(dex_modifier)
    d20 = roll_fn()
    return InitiativeRollResult(
        combatant_id=combatant_id,
        d20=d20,
        modifier=modifier,
    )


def sort_initiative_order(
    rolls: list[InitiativeRollResult],
) -> tuple[str, ...]:
    """
    Ordonne les combattants : total décroissant, puis ``combatant_id`` croissant.
    """
    ordered = sorted(
        rolls,
        key=lambda r: (-r.total, r.combatant_id),
    )
    return tuple(r.combatant_id for r in ordered)


def next_active_turn_index(
    initiative_order: tuple[str, ...],
    turn_index: int,
    *,
    is_active: Callable[[str], bool],
) -> tuple[int, int] | None:
    """
    Avance au prochain combattant actif.

    Retourne ``(nouvel_index, delta_round)`` où ``delta_round`` vaut 0 ou 1.
    Retourne ``None`` si aucun combattant actif dans la séquence.
    """
    if not initiative_order:
        return None
    n = len(initiative_order)
    idx = turn_index
    for _ in range(n):
        idx += 1
        delta_round = 0
        if idx >= n:
            idx = 0
            delta_round = 1
        combatant_id = initiative_order[idx]
        if is_active(combatant_id):
            return idx, delta_round
    return None
