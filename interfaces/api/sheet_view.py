# interfaces/api/sheet_view.py
"""Vue fiche fusionnée — overlay combat en lecture seule (contrat §2.6, ADR-005)."""
from __future__ import annotations

from jdr_engine.application.dto.output_serializers import (
    _active_effect_to_dict,
    character_sheet_to_dict,
)
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.persistence.combat_repository import CombatRecord, SqliteCombatRepository
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.engine import RuleEngine

from interfaces.api.combat_scope import find_open_combat_for_character


def find_open_combat_context(
    combat_repository: SqliteCombatRepository,
    character_id: str,
) -> tuple[CombatRecord, Combatant] | None:
    """Combat ouvert contenant ``character_id``, avec le combattant correspondant."""
    combat_id = find_open_combat_for_character(combat_repository, character_id)
    if combat_id is None:
        return None
    record = combat_repository.get_by_id(combat_id)
    if record is None:
        return None
    for combatant in record.state.combatants.values():
        if combatant.character_id == character_id:
            return record, combatant
    return None


def build_character_sheet_response(
    character: Character,
    engine: RuleEngine,
    combat_repository: SqliteCombatRepository,
    *,
    locale: str = "fr",
) -> dict:
    """
    Fiche calculée, fusionnée avec l'overlay combat si le personnage est engagé.

    Ne modifie jamais la fiche SQLite — overlay en lecture depuis le blob combat.
    """
    sheet = build_character_sheet(character, engine, locale=locale)
    payload = character_sheet_to_dict(sheet)
    context = find_open_combat_context(combat_repository, character.id)
    if context is None:
        return payload

    _record, combatant = context
    state = _record.state
    payload["hp_current"] = combatant.hp_current
    payload["hp_max"] = combatant.hp_max
    payload["ac"] = combatant.ac
    payload["active_effects"] = [
        _active_effect_to_dict(effect)
        for effect in state.active_effects
        if effect.target_id == combatant.combatant_id
    ]
    return payload
