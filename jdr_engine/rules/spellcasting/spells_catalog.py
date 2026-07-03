# jdr_engine/rules/spellcasting/spells_catalog.py
"""Catalogue sorts Lot B — Magicien & Clerc (SRD 2014 niv. 1-3)."""

WIZARD_SPELL_IDS: tuple[str, ...] = (
    "fire_bolt",
    "chromatic_orb",
    "burning_hands",
    "detect_magic",
    "scorching_ray",
)

CLERIC_SPELL_IDS: tuple[str, ...] = (
    "sacred_flame",
    "cure_wounds",
    "inflict_wounds",
    "bless",
    "spiritual_weapon",
)

SPELL_IDS_BY_CLASS: dict[str, tuple[str, ...]] = {
    "wizard": WIZARD_SPELL_IDS,
    "cleric": CLERIC_SPELL_IDS,
}

SUPPORTED_SPELLCASTING_CLASSES: tuple[str, ...] = ("wizard", "cleric")


def get_spell_ids_for_class(class_id: str) -> tuple[str, ...]:
    return SPELL_IDS_BY_CLASS.get(class_id, ())


def all_spellcasting_spell_ids() -> tuple[str, ...]:
    return WIZARD_SPELL_IDS + CLERIC_SPELL_IDS
