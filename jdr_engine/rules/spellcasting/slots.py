# jdr_engine/rules/spellcasting/slots.py
"""Emplacements de sorts — lanceurs complets, demi-lanceurs & magie de pacte SRD 2014."""
from __future__ import annotations

from jdr_engine.rules.spellcasting.spells_catalog import (
    FULL_CASTER_CLASSES,
    HALF_CASTER_CLASSES,
    PACT_CASTER_CLASSES,
    SUPPORTED_SPELLCASTING_CLASSES,
)

# Lanceur complet (PHB SRD 2014) — utilisé aussi pour les demi-lanceurs via niveau effectif
FULL_CASTER_SPELL_SLOTS: dict[int, dict[int, int]] = {
    1: {1: 2},
    2: {1: 3},
    3: {1: 4, 2: 2},
}

# Occultiste — magie de pacte (emplacements toujours au niveau max, recharge repos court)
PACT_CASTER_SPELL_SLOTS: dict[int, dict[int, int]] = {
    1: {1: 1},
    2: {1: 2},
    3: {2: 2},
}

# Rétrocompat tests / références directes (niv. 1–3)
HALF_CASTER_SPELL_SLOTS: dict[int, dict[int, int]] = {
    1: {},
    2: {1: 2},
    3: {1: 3},
}


def half_caster_effective_full_level(character_level: int) -> int | None:
    """
    Niveau de lanceur complet équivalent (SRD 2014) : ⌈niv/2⌉.

    Retourne ``None`` au niv. 1 (aucun emplacement).
    """
    if character_level < 2:
        return None
    return (character_level + 1) // 2


def get_half_caster_max_spell_slots(level: int) -> dict[int, int]:
    """Emplacements demi-lanceur — progression via table lanceur complet (niv. 1–5)."""
    if level < 1 or level > 5:
        return {}
    effective = half_caster_effective_full_level(level)
    if effective is None:
        return {}
    table = FULL_CASTER_SPELL_SLOTS.get(effective, {})
    return {k: v for k, v in table.items() if k in (1, 2)}


def get_max_spell_slots(class_id: str, level: int) -> dict[int, int]:
    """Retourne {niveau_sort: nombre} pour les slots niv. 1 et 2 uniquement."""
    if class_id not in SUPPORTED_SPELLCASTING_CLASSES or level < 1:
        return {}
    if class_id in FULL_CASTER_CLASSES:
        if level > 3:
            return {}
        table = FULL_CASTER_SPELL_SLOTS.get(level, {})
    elif class_id in HALF_CASTER_CLASSES:
        if level > 3:
            return {}
        return get_half_caster_max_spell_slots(level)
    elif class_id in PACT_CASTER_CLASSES:
        if level > 3:
            return {}
        table = PACT_CASTER_SPELL_SLOTS.get(level, {})
    else:
        return {}
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
