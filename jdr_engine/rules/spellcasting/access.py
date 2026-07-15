# jdr_engine/rules/spellcasting/access.py
"""Accès à l'incantation selon niveau de classe (demi-lanceurs niv. 2+)."""
from __future__ import annotations

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.spells_catalog import (
    HALF_CASTER_CLASSES,
    SUPPORTED_SPELLCASTING_CLASSES,
)
from jdr_engine.rules.spellcasting.state import get_spellcasting_state


def spellcasting_start_level(engine: RuleEngine, class_id: str) -> int:
    entry = engine.get_entity("class", class_id)
    if entry is None:
        return 1
    mechanics = entry.definition.mechanics
    pact = mechanics.get("pact_magic") or {}
    if isinstance(pact, dict) and pact.get("ability"):
        return int(pact.get("level", 1))
    spellcasting = mechanics.get("spellcasting") or {}
    return int(spellcasting.get("level", 1))


def has_spellcasting_access(
    character: Character,
    engine: RuleEngine,
) -> bool:
    if character.class_id not in SUPPORTED_SPELLCASTING_CLASSES:
        return False
    if character.class_id in HALF_CASTER_CLASSES:
        state = get_spellcasting_state(character)
        if state.get("spells_prepared") or state.get("spells_known"):
            return True
    return character.level >= spellcasting_start_level(engine, character.class_id)
