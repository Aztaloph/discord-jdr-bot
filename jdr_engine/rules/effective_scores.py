# jdr_engine/rules/effective_scores.py
"""Scores effectifs d'un personnage — base persistée + bonus raciaux compendium."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.effective_scores import (
    compute_effective_ability_scores,
    effective_ability_modifier,
)
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.racial.resolve import get_racial_ability_bonuses


def get_effective_ability_scores(
    character: Character,
    engine: RuleEngine,
) -> dict[str, int]:
    """Scores utilisés pour modificateurs, DD sorts et quotas préparés."""
    ability_ids = [a.id for a in engine.registry.config.abilities] or list(
        DEFAULT_ABILITY_IDS
    )
    base_scores = character.ability_scores.with_defaults(ability_ids).scores
    racial_bonuses = get_racial_ability_bonuses(character, engine)
    return compute_effective_ability_scores(base_scores, racial_bonuses)


def get_effective_ability_modifier(
    character: Character,
    engine: RuleEngine,
    ability_id: str,
) -> int:
    """Modificateur effectif d'une caractéristique (base + racial)."""
    scores = get_effective_ability_scores(character, engine)
    return effective_ability_modifier(scores, ability_id)
