# jdr_engine/rules/effects/collect.py
"""Adaptateurs registre → effects[] — lot ADR-006 décision 3."""
from __future__ import annotations

from typing import Any

from jdr_engine.rules.combat.buffs.collect import (
    collect_buff_roll_effects as _translate_buff_roll_effects,
)
from jdr_engine.rules.combat.buffs.hunters_mark import hunters_mark_bonus_applies
from jdr_engine.rules.combat.buffs.hex import hex_bonus_applies
from jdr_engine.rules.combat.conditions.catalog import PHASE1_CONDITIONS
from jdr_engine.rules.effects.registry import ActiveEffectRegistry


def collect_buff_roll_effects(
    registry: ActiveEffectRegistry,
    combatant_id: str,
) -> list[dict[str, Any]]:
    """Traduit les buffs actifs du registre en effets ``d20.py`` pour un combattant."""
    return _translate_buff_roll_effects(
        combatant_id,
        registry.query(target_id=combatant_id),
    )


def collect_condition_roll_effects(
    registry: ActiveEffectRegistry,
    combatant_id: str,
) -> list[dict[str, Any]]:
    """Traduit les conditions phase 1 du registre en effets ``d20.py``."""
    effects: list[dict[str, Any]] = []
    for effect in registry.query(target_id=combatant_id):
        if effect.effect_id not in PHASE1_CONDITIONS:
            continue
        for context in ("attack", "ability_check"):
            effects.append(
                {
                    "type": "disadvantage",
                    "context": context,
                    "source_id": effect.effect_id,
                }
            )
    return effects


def hunters_mark_bonus_applies_for_target(
    registry: ActiveEffectRegistry,
    target_id: str,
    source_id: str | None,
) -> bool:
    """Vrai si la cible porte une marque du chasseur posée par ``source_id``."""
    return hunters_mark_bonus_applies(
        registry.query(target_id=target_id),
        source_id,
    )


def hex_bonus_applies_for_target(
    registry: ActiveEffectRegistry,
    target_id: str,
    source_id: str | None,
) -> bool:
    """Vrai si la cible porte un maléfice posé par ``source_id``."""
    return hex_bonus_applies(
        registry.query(target_id=target_id),
        source_id,
    )
