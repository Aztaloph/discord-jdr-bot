# jdr_engine/rules/spellcasting/slots.py
"""Emplacements de sorts — lanceurs complets SRD 2014 (niv. 1-3, slots 1-2)."""
from __future__ import annotations

from jdr_engine.rules.spellcasting.spells_catalog import SUPPORTED_SPELLCASTING_CLASSES

# Magicien & Clerc — table lanceur complet (SRD 5.1 2014, PHB)
FULL_CASTER_SPELL_SLOTS: dict[int, dict[int, int]] = {
    1: {1: 2},
    2: {1: 3},
    3: {1: 4, 2: 2},
}


def get_max_spell_slots(class_id: str, level: int) -> dict[int, int]:
    """Retourne {niveau_sort: nombre} pour les slots niv. 1 et 2 uniquement."""
    if class_id not in SUPPORTED_SPELLCASTING_CLASSES or level < 1 or level > 3:
        return {}
    table = FULL_CASTER_SPELL_SLOTS.get(level, {})
    return {k: v for k, v in table.items() if k in (1, 2)}


def get_remaining_slots(
    class_id: str,
    level: int,
    slots_used: dict[int, int],
) -> dict[int, int]:
    """Slots restants par niveau de sort."""
    max_slots = get_max_spell_slots(class_id, level)
    return {
        slot_level: max_slots[slot_level] - slots_used.get(slot_level, 0)
        for slot_level in max_slots
    }
