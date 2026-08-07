# jdr_engine/rules/effects/collect.py
"""Adaptateurs registre → effects[] — lot ADR-006 décision 3."""
from __future__ import annotations

from typing import Any

from jdr_engine.rules.combat.buffs.collect import (
    collect_buff_roll_effects as _translate_buff_roll_effects,
)
from jdr_engine.rules.combat.buffs.hunters_mark import hunters_mark_bonus_applies
from jdr_engine.rules.combat.buffs.hex import hex_bonus_applies
from jdr_engine.rules.effects.registry import ActiveEffectRegistry

# Effets émis pour les conditions portées par le **jeteur** (attaquant ou sujet du jet).
_ATTACKER_CONDITION_EFFECTS: dict[str, list[dict[str, Any]]] = {
    "frightened": [
        {"type": "disadvantage", "context": "attack"},
        {"type": "disadvantage", "context": "ability_check"},
    ],
    "poisoned": [
        {"type": "disadvantage", "context": "attack"},
        {"type": "disadvantage", "context": "ability_check"},
    ],
    "prone": [
        {"type": "disadvantage", "context": "attack"},
    ],
}

# Effets émis pour les conditions portées par le **défenseur** lors d'un jet d'attaque.
_DEFENDER_CONDITION_ATTACK_EFFECTS: dict[str, list[dict[str, Any]]] = {
    "prone": [
        {
            "type": "advantage",
            "context": "attack",
            "when": "target_prone_melee",
        },
        {
            "type": "disadvantage",
            "context": "attack",
            "when": "target_prone_ranged",
        },
    ],
}


def _emit_mapped_condition_effects(
    registry: ActiveEffectRegistry,
    combatant_id: str,
    mapping: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Traduit les conditions actives selon un mapping id → templates d'effets."""
    effects: list[dict[str, Any]] = []
    for active in registry.query(target_id=combatant_id):
        templates = mapping.get(active.effect_id)
        if templates is None:
            continue
        for template in templates:
            effect = dict(template)
            effect.setdefault("source_id", active.effect_id)
            effects.append(effect)
    return effects


def collect_buff_roll_effects(
    registry: ActiveEffectRegistry,
    combatant_id: str,
) -> list[dict[str, Any]]:
    """Traduit les buffs actifs du registre en effets ``d20.py`` pour un combattant."""
    return _translate_buff_roll_effects(
        combatant_id,
        registry.query(target_id=combatant_id),
    )


def collect_attacker_condition_roll_effects(
    registry: ActiveEffectRegistry,
    combatant_id: str,
) -> list[dict[str, Any]]:
    """Traduit les conditions phase 1 du jeteur en effets ``d20.py``."""
    return _emit_mapped_condition_effects(
        registry,
        combatant_id,
        _ATTACKER_CONDITION_EFFECTS,
    )


def collect_defender_condition_roll_effects(
    registry: ActiveEffectRegistry,
    defender_id: str,
) -> list[dict[str, Any]]:
    """Traduit les conditions du défenseur en effets d'attaque (portée, etc.)."""
    return _emit_mapped_condition_effects(
        registry,
        defender_id,
        _DEFENDER_CONDITION_ATTACK_EFFECTS,
    )


def collect_condition_roll_effects(
    registry: ActiveEffectRegistry,
    combatant_id: str,
) -> list[dict[str, Any]]:
    """Alias rétrocompat — effets conditions côté jeteur."""
    return collect_attacker_condition_roll_effects(registry, combatant_id)


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
