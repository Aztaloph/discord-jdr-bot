# jdr_engine/rules/spellcasting/state.py
"""État persistant emplacements / grimoire (character.choices.spellcasting)."""
from __future__ import annotations

from typing import Any

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots, get_remaining_slots


class SpellcastingStateError(Exception):
    pass


def get_spellcasting_state(character: Character) -> dict[str, Any]:
    """Lit choices.spellcasting (dict vide si absent)."""
    raw = (character.choices or {}).get("spellcasting")
    return dict(raw) if isinstance(raw, dict) else {}


def get_slots_used(character: Character) -> dict[int, int]:
    state = get_spellcasting_state(character)
    used = state.get("slots_used") or {}
    if not isinstance(used, dict):
        return {}
    return {int(k): int(v) for k, v in used.items()}


def get_cantrips_known(character: Character) -> list[str]:
    state = get_spellcasting_state(character)
    raw = state.get("cantrips_known") or []
    return [str(s) for s in raw] if isinstance(raw, list) else []


def get_spells_prepared(character: Character) -> list[str]:
    state = get_spellcasting_state(character)
    raw = state.get("spells_prepared") or []
    return [str(s) for s in raw] if isinstance(raw, list) else []


def spell_is_available(character: Character, spell_id: str) -> bool:
    spell_level = _spell_level_from_lists(character, spell_id)
    if spell_level == 0:
        return spell_id in get_cantrips_known(character)
    return spell_id in get_spells_prepared(character)


def _spell_level_from_lists(character: Character, spell_id: str) -> int | None:
    if spell_id in get_cantrips_known(character):
        return 0
    if spell_id in get_spells_prepared(character):
        return None  # resolved from compendium at cast time
    return None


def consume_spell_slot(character: Character, spell_level: int) -> Character:
    """
    Consomme un emplacement de niveau ``spell_level`` (ou supérieur si épuisé).

    SRD : lancer un sort de niv. X consomme un slot de niv. X (ou supérieur).
    """
    if spell_level <= 0:
        return character

    max_slots = get_max_spell_slots(character.class_id, character.level)
    used = get_slots_used(character)

    slot_to_use = _find_slot_to_consume(spell_level, max_slots, used)
    if slot_to_use is None:
        raise SpellcastingStateError(
            f"Aucun emplacement de sort niv. {spell_level}+ disponible."
        )

    used[slot_to_use] = used.get(slot_to_use, 0) + 1
    return _update_spellcasting(character, slots_used=used)


def _find_slot_to_consume(
    spell_level: int,
    max_slots: dict[int, int],
    used: dict[int, int],
) -> int | None:
    for level in sorted(max_slots.keys()):
        if level < spell_level:
            continue
        remaining = max_slots[level] - used.get(level, 0)
        if remaining > 0:
            return level
    return None


def reset_spell_slots(character: Character) -> Character:
    """Repos long — réinitialise slots_used."""
    return _update_spellcasting(character, slots_used={})


def _update_spellcasting(
    character: Character,
    *,
    slots_used: dict[int, int] | None = None,
) -> Character:
    choices = dict(character.choices or {})
    state = get_spellcasting_state(character)
    if slots_used is not None:
        state["slots_used"] = {str(k): v for k, v in slots_used.items()}
    choices["spellcasting"] = state
    character.choices = choices
    return character


def format_slots_display(character: Character) -> str:
    """Texte compact pour embed Discord."""
    max_slots = get_max_spell_slots(character.class_id, character.level)
    if not max_slots:
        return "Aucun emplacement (non-magicien ou niv. > 3)"
    used = get_slots_used(character)
    remaining = get_remaining_slots(character.class_id, character.level, used)
    parts = []
    for level in sorted(max_slots.keys()):
        parts.append(f"niv.{level}: {remaining[level]}/{max_slots[level]}")
    return ", ".join(parts)
