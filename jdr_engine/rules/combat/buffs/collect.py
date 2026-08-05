# jdr_engine/rules/combat/buffs/collect.py
"""Collecteur unidirectionnel — effets actifs du combattant → effects[] pour d20."""
from __future__ import annotations

from typing import Any

from jdr_engine.domain.combat.active_effect import ActiveEffect


def collect_buff_roll_effects(
    combatant_id: str,
    active_effects: tuple[ActiveEffect, ...],
) -> list[dict[str, Any]]:
    """
    Traduit les buffs ``ActiveEffect`` en effets ``d20.py``.

    Unidirectionnel : n'affecte que les jets **du** combattant ``combatant_id``.
    """
    effects: list[dict[str, Any]] = []
    for effect in active_effects:
        if effect.target_id != combatant_id:
            continue
        if effect.effect_id == "blessed":
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
