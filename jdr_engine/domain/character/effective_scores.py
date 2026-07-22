# jdr_engine/domain/character/effective_scores.py
"""Scores effectifs = base (point buy / ASI) + bonus raciaux."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import ability_modifier


def compute_effective_ability_scores(
    base_scores: dict[str, int],
    racial_bonuses: dict[str, int],
) -> dict[str, int]:
    """Applique les bonus raciaux sur les scores de base (sans double comptage)."""
    effective = dict(base_scores)
    for ability_id, bonus in racial_bonuses.items():
        effective[ability_id] = effective.get(ability_id, 10) + bonus
    return effective


def effective_ability_modifier(effective_scores: dict[str, int], ability_id: str) -> int:
    """Modificateur D&D 5e depuis un dict de scores effectifs."""
    return ability_modifier(effective_scores.get(ability_id, 10))
