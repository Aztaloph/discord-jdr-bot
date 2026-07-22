# jdr_engine/rules/spellcasting/slots.py
"""Emplacements de sorts — lanceurs complets, demi-lanceurs & magie de pacte SRD 2014."""
from __future__ import annotations

from jdr_engine.rules.spellcasting.spells_catalog import (
    FULL_CASTER_CLASSES,
    HALF_CASTER_CLASSES,
    PACT_CASTER_CLASSES,
    SUPPORTED_SPELLCASTING_CLASSES,
)

# Lanceur complet — PHB / SRD 2014 (niv. personnage 1–20, données pures)
FULL_CASTER_SPELL_SLOTS: dict[int, dict[int, int]] = {
    1: {1: 2},
    2: {1: 3},
    3: {1: 4, 2: 2},
    4: {1: 4, 2: 3, 3: 1},
    5: {1: 4, 2: 3, 3: 2},
    6: {1: 4, 2: 3, 3: 3},
    7: {1: 4, 2: 3, 3: 3, 4: 1},
    8: {1: 4, 2: 3, 3: 3, 4: 2},
    9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
}

# Occultiste — magie de pacte (emplacements toujours au niveau max, recharge repos court)
PACT_CASTER_SPELL_SLOTS: dict[int, dict[int, int]] = {
    1: {1: 1},
    2: {1: 2},
    3: {2: 2},
    4: {2: 2},
    5: {3: 2},
}

# Rétrocompat tests / références directes (demi-lanceur niv. 1–3, emplacements visibles)
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
    """Emplacements demi-lanceur — progression via table lanceur complet."""
    if level < 1:
        return {}
    effective = half_caster_effective_full_level(level)
    if effective is None:
        return {}
    table = FULL_CASTER_SPELL_SLOTS.get(effective, {})
    # Demi-lanceur : emplacements de sorts ≤ 5 (SRD) — filtré par niveau effectif
    max_spell_level = max(1, (effective + 1) // 2)
    return {k: v for k, v in table.items() if k <= max_spell_level}


def get_max_spell_slots(class_id: str, level: int) -> dict[int, int]:
    """Retourne {niveau_sort: nombre} selon la table SRD 2014."""
    if class_id not in SUPPORTED_SPELLCASTING_CLASSES or level < 1:
        return {}
    if class_id in FULL_CASTER_CLASSES:
        return dict(FULL_CASTER_SPELL_SLOTS.get(level, {}))
    if class_id in HALF_CASTER_CLASSES:
        return get_half_caster_max_spell_slots(level)
    if class_id in PACT_CASTER_CLASSES:
        return dict(PACT_CASTER_SPELL_SLOTS.get(level, {}))
    return {}


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
