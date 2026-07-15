# jdr_engine/rules/spellcasting/pools.py
"""Pools de sorts par classe — filtrage par niveau d'emplacement (P0)."""
from __future__ import annotations

from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
from jdr_engine.rules.spellcasting.spell_levels import get_spell_level
from jdr_engine.rules.spellcasting.spells_catalog import (
    BARD_CANTRIP_IDS,
    BARD_SPELL_IDS,
    CLERIC_CANTRIP_IDS,
    CLERIC_SPELL_IDS,
    DRUID_CANTRIP_IDS,
    DRUID_SPELL_IDS,
    PALADIN_SPELL_IDS,
    RANGER_SPELL_IDS,
    SORCERER_CANTRIP_IDS,
    SORCERER_SPELL_IDS,
    WARLOCK_CANTRIP_IDS,
    WARLOCK_SPELL_IDS,
    WIZARD_CANTRIP_IDS,
    WIZARD_SPELLBOOK_POOL,
    get_spell_ids_for_class,
)

_CANTrip_POOL_BY_CLASS: dict[str, tuple[str, ...]] = {
    "wizard": WIZARD_CANTRIP_IDS,
    "sorcerer": SORCERER_CANTRIP_IDS,
    "cleric": CLERIC_CANTRIP_IDS,
    "bard": BARD_CANTRIP_IDS,
    "druid": DRUID_CANTRIP_IDS,
    "warlock": WARLOCK_CANTRIP_IDS,
}

_LEVELED_POOL_BY_CLASS: dict[str, tuple[str, ...]] = {
    "wizard": WIZARD_SPELLBOOK_POOL,
    "sorcerer": SORCERER_SPELL_IDS,
    "cleric": CLERIC_SPELL_IDS,
    "bard": tuple(s for s in BARD_SPELL_IDS if s not in BARD_CANTRIP_IDS),
    "druid": DRUID_SPELL_IDS,
    "warlock": WARLOCK_SPELL_IDS,
    "ranger": RANGER_SPELL_IDS,
    "paladin": PALADIN_SPELL_IDS,
}


def get_cantrip_pool(class_id: str) -> tuple[str, ...]:
    """Tours de magie disponibles pour la classe (catalogue curated)."""
    return _CANTrip_POOL_BY_CLASS.get(class_id, ())


def get_leveled_spell_pool(class_id: str) -> tuple[str, ...]:
    """Sorts niv. 1+ du catalogue curated (hors cantrips)."""
    if class_id in _LEVELED_POOL_BY_CLASS:
        return _LEVELED_POOL_BY_CLASS[class_id]
    return tuple(
        s
        for s in get_spell_ids_for_class(class_id)
        if s not in get_cantrip_pool(class_id)
    )


def get_class_spell_pool(
    class_id: str,
    *,
    include_cantrips: bool = True,
) -> tuple[str, ...]:
    """Union cantrips + sorts niv. 1+."""
    parts: list[str] = []
    if include_cantrips:
        parts.extend(get_cantrip_pool(class_id))
    parts.extend(get_leveled_spell_pool(class_id))
    seen: list[str] = []
    for spell_id in parts:
        if spell_id not in seen:
            seen.append(spell_id)
    return tuple(seen)


def max_castable_spell_level(class_id: str, character_level: int) -> int:
    """Niveau d'emplacement max lançable à ce niveau de personnage."""
    slots = get_max_spell_slots(class_id, character_level)
    if not slots:
        return 0
    return max(slots.keys())


def filter_spells_by_max_level(
    spell_ids: tuple[str, ...] | list[str],
    max_spell_level: int,
    *,
    engine: RuleEngine | None = None,
) -> list[str]:
    """Conserve les sorts dont le niveau d'emplacement ≤ ``max_spell_level``."""
    if max_spell_level <= 0:
        return []
    return [
        spell_id
        for spell_id in spell_ids
        if get_spell_level(spell_id, engine=engine) <= max_spell_level
    ]


def get_filtered_leveled_pool(
    class_id: str,
    character_level: int,
    *,
    engine: RuleEngine | None = None,
) -> list[str]:
    """
    Sorts niv. 1+ de la classe filtrés par emplacements disponibles.

    Utilisé pour proposer les choix au level-up / à la préparation (P2+).
    """
    pool = get_leveled_spell_pool(class_id)
    max_level = max_castable_spell_level(class_id, character_level)
    return filter_spells_by_max_level(pool, max_level, engine=engine)


def spell_id_in_class_pool(class_id: str, spell_id: str) -> bool:
    return spell_id in get_class_spell_pool(class_id, include_cantrips=True)
