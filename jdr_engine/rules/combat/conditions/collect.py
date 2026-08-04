# jdr_engine/rules/combat/conditions/collect.py
"""Collecteur unidirectionnel — conditions du combattant → effects[] pour d20."""
from __future__ import annotations

from typing import Any

from jdr_engine.domain.combat.combatant import Combatant

_ATTACK_AND_ABILITY_CHECK = frozenset({"frightened", "poisoned"})


def collect_condition_roll_effects(combatant: Combatant) -> list[dict[str, Any]]:
    """
    Traduit les conditions overlay du combattant en effets ``d20.py``.

    Unidirectionnel : n'affecte que les jets **du** combattant concerné.
    Aucune logique d'annulation — déléguée à ``_resolve_mode``.
    """
    effects: list[dict[str, Any]] = []
    for condition_id in combatant.conditions:
        if condition_id not in _ATTACK_AND_ABILITY_CHECK:
            continue
        for context in ("attack", "ability_check"):
            effects.append(
                {
                    "type": "disadvantage",
                    "context": context,
                    "source_id": condition_id,
                }
            )
    return effects
