# jdr_engine/rules/combat/attack_roll.py
"""
Résolution du toucher — jet d'attaque vs CA (lot C3a).

Utilise ``D20RollResult`` produit par ``roll_d20`` / ``roll_d20_for_character``.
Le critique et l'échec automatique court-circuitent la comparaison à la CA (SRD 5.1).
"""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.dice.d20 import D20RollResult


@dataclass(frozen=True)
class AttackHitOutcome:
    """Résultat du toucher après jet de d20."""

    hit: bool
    critical: bool
    automatic_miss: bool
    target_ac: int


def resolve_attack_hit(d20_result: D20RollResult, target_ac: int) -> AttackHitOutcome:
    """
    Détermine toucher, critique et échec automatique.

    - Nat 1 : manque (``automatic_miss``), quelle que soit la CA.
    - Nat 20 : touche (``critical``), sans comparer à la CA.
    - Sinon : ``total >= target_ac``.
    """
    if d20_result.natural_1:
        return AttackHitOutcome(
            hit=False,
            critical=False,
            automatic_miss=True,
            target_ac=target_ac,
        )
    if d20_result.natural_20:
        return AttackHitOutcome(
            hit=True,
            critical=True,
            automatic_miss=False,
            target_ac=target_ac,
        )
    return AttackHitOutcome(
        hit=d20_result.total >= target_ac,
        critical=False,
        automatic_miss=False,
        target_ac=target_ac,
    )
