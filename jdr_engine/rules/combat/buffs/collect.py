# jdr_engine/rules/combat/buffs/collect.py
"""Collecteur unidirectionnel — buffs overlay du combattant → effects[] pour d20."""
from __future__ import annotations

from typing import Any

from jdr_engine.domain.combat.combatant import Combatant


def collect_buff_roll_effects(combatant: Combatant) -> list[dict[str, Any]]:
    """
    Traduit les buffs overlay actifs en effets ``d20.py``.

    Unidirectionnel : n'affecte que les jets **du** combattant concerné.
    """
    effects: list[dict[str, Any]] = []
    if combatant.blessed:
        for context in ("attack", "saving_throw"):
            effects.append(
                {
                    "type": "roll_bonus_dice",
                    "dice": "1d4",
                    "context": context,
                    "source_id": "bless",
                }
            )
    return effects
