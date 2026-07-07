# jdr_engine/rules/spellcasting/spells_catalog.py
"""Catalogue sorts — lanceurs complets & demi-lanceurs (SRD 2014 niv. 1-3)."""

WIZARD_CANTRIP_IDS: tuple[str, ...] = (
    "fire_bolt",
    "thaumaturgy",
    "guidance",
    "vicious_mockery",
)

WIZARD_SPELLBOOK_POOL: tuple[str, ...] = (
    "chromatic_orb",
    "burning_hands",
    "detect_magic",
    "magic_missile",
    "shield",
    "hellish_rebuke",
    "scorching_ray",
    "darkness",
    "inflict_wounds",
    "bless",
)

WIZARD_SPELL_IDS: tuple[str, ...] = WIZARD_CANTRIP_IDS + WIZARD_SPELLBOOK_POOL

SORCERER_CANTRIP_IDS: tuple[str, ...] = (
    "fire_bolt",
    "thaumaturgy",
    "guidance",
    "vicious_mockery",
    "sacred_flame",
)

SORCERER_SPELL_IDS: tuple[str, ...] = (
    "chromatic_orb",
    "burning_hands",
    "detect_magic",
    "magic_missile",
    "shield",
    "scorching_ray",
    "hellish_rebuke",
)

CLERIC_CANTRIP_IDS: tuple[str, ...] = (
    "sacred_flame",
    "guidance",
    "thaumaturgy",
)

CLERIC_SPELL_IDS: tuple[str, ...] = (
    "cure_wounds",
    "inflict_wounds",
    "bless",
    "detect_magic",
    "spiritual_weapon",
)

BARD_CANTRIP_IDS: tuple[str, ...] = (
    "vicious_mockery",
    "thaumaturgy",
)

BARD_SPELL_IDS: tuple[str, ...] = (
    "vicious_mockery",
    "thaumaturgy",
    "cure_wounds",
    "healing_word",
    "detect_magic",
    "bless",
)

RANGER_SPELL_IDS: tuple[str, ...] = (
    "hunters_mark",
    "cure_wounds",
    "detect_magic",
)

PALADIN_SPELL_IDS: tuple[str, ...] = (
    "bless",
    "cure_wounds",
    "detect_magic",
)

DRUID_CANTRIP_IDS: tuple[str, ...] = (
    "druidcraft",
    "produce_flame",
    "guidance",
)

DRUID_SPELL_IDS: tuple[str, ...] = (
    "entangle",
    "cure_wounds",
    "faerie_fire",
    "flaming_sphere",
)

WARLOCK_CANTRIP_IDS: tuple[str, ...] = (
    "eldritch_blast",
    "prestidigitation",
)

WARLOCK_SPELL_IDS: tuple[str, ...] = (
    "hex",
    "armor_of_agathys",
    "darkness",
)

SPELL_IDS_BY_CLASS: dict[str, tuple[str, ...]] = {
    "wizard": WIZARD_SPELL_IDS,
    "sorcerer": SORCERER_CANTRIP_IDS + SORCERER_SPELL_IDS,
    "cleric": CLERIC_CANTRIP_IDS + CLERIC_SPELL_IDS,
    "bard": BARD_SPELL_IDS,
    "ranger": RANGER_SPELL_IDS,
    "paladin": PALADIN_SPELL_IDS,
    "druid": DRUID_CANTRIP_IDS + DRUID_SPELL_IDS,
    "warlock": WARLOCK_CANTRIP_IDS + WARLOCK_SPELL_IDS,
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
    return SPELL_IDS_BY_CLASS.get(class_id, ())


def all_spellcasting_spell_ids() -> tuple[str, ...]:
    seen: list[str] = []
    for class_id in SUPPORTED_SPELLCASTING_CLASSES:
        for spell_id in get_spell_ids_for_class(class_id):
            if spell_id not in seen:
                seen.append(spell_id)
    return tuple(seen)
