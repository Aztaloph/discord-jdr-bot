# jdr_engine/rules/spellcasting/spells_catalog.py
"""Catalogue sorts — pools dérivés du compendium YAML (Lot B2 — D2)."""

from __future__ import annotations

from jdr_engine.rules.spellcasting.spell_pool_builder import (
    all_spellcasting_spell_ids as _all_spellcasting_spell_ids,
    build_class_spell_pools,
    spell_ids_for_class as _spell_ids_for_class,
)

_CANTrip_POOLS, _LEVELED_POOLS = build_class_spell_pools()

WIZARD_CANTRIP_IDS: tuple[str, ...] = _CANTrip_POOLS.get("wizard", ())
WIZARD_SPELLBOOK_POOL: tuple[str, ...] = _LEVELED_POOLS.get("wizard", ())
WIZARD_SPELL_IDS: tuple[str, ...] = WIZARD_CANTRIP_IDS + WIZARD_SPELLBOOK_POOL

SORCERER_CANTRIP_IDS: tuple[str, ...] = _CANTrip_POOLS.get("sorcerer", ())
SORCERER_SPELL_IDS: tuple[str, ...] = _LEVELED_POOLS.get("sorcerer", ())

CLERIC_CANTRIP_IDS: tuple[str, ...] = _CANTrip_POOLS.get("cleric", ())
CLERIC_SPELL_IDS: tuple[str, ...] = _LEVELED_POOLS.get("cleric", ())

BARD_CANTRIP_IDS: tuple[str, ...] = _CANTrip_POOLS.get("bard", ())
BARD_SPELL_IDS: tuple[str, ...] = _CANTrip_POOLS.get("bard", ()) + tuple(
    s for s in _LEVELED_POOLS.get("bard", ()) if s not in _CANTrip_POOLS.get("bard", ())
)

RANGER_SPELL_IDS: tuple[str, ...] = _LEVELED_POOLS.get("ranger", ())
PALADIN_SPELL_IDS: tuple[str, ...] = _LEVELED_POOLS.get("paladin", ())

DRUID_CANTRIP_IDS: tuple[str, ...] = _CANTrip_POOLS.get("druid", ())
DRUID_SPELL_IDS: tuple[str, ...] = _LEVELED_POOLS.get("druid", ())

WARLOCK_CANTRIP_IDS: tuple[str, ...] = _CANTrip_POOLS.get("warlock", ())
WARLOCK_SPELL_IDS: tuple[str, ...] = _LEVELED_POOLS.get("warlock", ())

SPELL_IDS_BY_CLASS: dict[str, tuple[str, ...]] = {
    class_id: _spell_ids_for_class(class_id)
    for class_id in (
        "wizard",
        "sorcerer",
        "cleric",
        "bard",
        "ranger",
        "paladin",
        "druid",
        "warlock",
    )
}

FULL_CASTER_CLASSES: tuple[str, ...] = (
    "wizard",
    "cleric",
    "bard",
    "sorcerer",
    "druid",
)
HALF_CASTER_CLASSES: tuple[str, ...] = ("ranger", "paladin")
PACT_CASTER_CLASSES: tuple[str, ...] = ("warlock",)

SUPPORTED_SPELLCASTING_CLASSES: tuple[str, ...] = (
    FULL_CASTER_CLASSES + HALF_CASTER_CLASSES + PACT_CASTER_CLASSES
)


def get_spell_ids_for_class(class_id: str) -> tuple[str, ...]:
    return SPELL_IDS_BY_CLASS.get(class_id, _spell_ids_for_class(class_id))


def all_spellcasting_spell_ids() -> tuple[str, ...]:
    return _all_spellcasting_spell_ids()
