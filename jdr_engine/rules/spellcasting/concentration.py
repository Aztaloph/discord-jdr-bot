# jdr_engine/rules/spellcasting/concentration.py
"""Concentration active — point d'entrée unique (ADR-004 §2, lot C5)."""
from __future__ import annotations

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.spellcasting.state import get_spellcasting_state


def get_active_concentration(character: Character) -> dict[str, str] | None:
    """Retourne ``{spell_id, spell_name}`` si concentration active, sinon ``None``."""
    state = get_spellcasting_state(character)
    raw = state.get("concentration")
    if not isinstance(raw, dict):
        return None
    spell_id = str(raw.get("spell_id", "")).strip()
    if not spell_id:
        return None
    spell_name = str(raw.get("spell_name") or spell_id)
    return {"spell_id": spell_id, "spell_name": spell_name}


def set_concentration(
    character: Character,
    spell_id: str,
    spell_name: str,
) -> tuple[Character, str | None]:
    """
    Pose ou remplace la concentration active.

    Retourne le nom localisé du sort interrompu, ou ``None`` si aucun remplacement
    (pas de concentration antérieure, ou recast du même sort).
    """
    choices = dict(character.choices or {})
    state = dict(get_spellcasting_state(character))
    previous = state.get("concentration")
    interrupted_name: str | None = None
    if isinstance(previous, dict):
        previous_id = str(previous.get("spell_id", ""))
        if previous_id and previous_id != spell_id:
            interrupted_name = str(previous.get("spell_name") or previous_id)
    state["concentration"] = {"spell_id": spell_id, "spell_name": spell_name}
    choices["spellcasting"] = state
    character.choices = choices
    return character, interrupted_name


def clear_concentration(character: Character) -> Character:
    """Retire la concentration active (repos, rupture sur dégâts, etc.)."""
    state = get_spellcasting_state(character)
    if "concentration" not in state:
        return character
    state = dict(state)
    state.pop("concentration", None)
    choices = dict(character.choices or {})
    choices["spellcasting"] = state
    character.choices = choices
    return character
