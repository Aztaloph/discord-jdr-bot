# jdr_engine/rules/spellcasting/model.py
"""
Taxonomie lanceurs de sorts SRD 2014 — Passe 2 / Lot P0.

Trois familles :
- ``KNOWN_FIXED`` : sorts connus fixes (barde, ensorceleur, occultiste)
- ``PREPARED`` : liste de classe + sous-ensemble préparé (clerc, druide, rôdeur, paladin)
- ``WIZARD_HYBRID`` : grimoire + préparation quotidienne

Schéma ``choices.spellcasting`` par famille (clés persistées SQLite) :

KNOWN_FIXED
    cantrips_known, spells_known, slots_used
    (+ pact_magic pour occultiste)

PREPARED
    cantrips_known, spells_prepared, slots_used
    (+ domain_spells pour clerc — toujours préparés, hors quota)

WIZARD_HYBRID
    cantrips_known, spellbook, spells_prepared, slots_used

Note P1 : le barde duplique aujourd'hui ``spells_prepared`` (= ``spells_known``) ;
à retirer lors du nettoyage P1.
"""
from __future__ import annotations

from enum import Enum

from jdr_engine.rules.spellcasting.spells_catalog import SUPPORTED_SPELLCASTING_CLASSES

# ── Quotas SRD 2014 — full casters niv. 1–20 (Lot A1) ; autres classes niv. 1–3 ─

def _tiered_cantrips_by_level(
    *,
    through_a: int,
    count_a: int,
    through_b: int,
    count_b: int,
    count_c: int,
) -> dict[int, int]:
    """Cantrips connus par palier SRD (ex. magicien : 3 → 4 → 5)."""
    return {
        level: (
            count_a
            if level <= through_a
            else count_b
            if level <= through_b
            else count_c
        )
        for level in range(1, 21)
    }


def wizard_spellbook_capacity_at_level(level: int) -> int:
    """SRD 2014 : 6 sorts au niv. 1, +2 par niveau de magicien."""
    if level < 1:
        return 0
    return 6 + 2 * (level - 1)


# Full casters — cantrips 1–20
WIZARD_CANTRIPS_BY_LEVEL: dict[int, int] = _tiered_cantrips_by_level(
    through_a=2, count_a=3, through_b=9, count_b=4, count_c=5
)
CLERIC_CANTRIPS_BY_LEVEL: dict[int, int] = _tiered_cantrips_by_level(
    through_a=3, count_a=3, through_b=9, count_b=4, count_c=5
)
DRUID_CANTRIPS_BY_LEVEL: dict[int, int] = _tiered_cantrips_by_level(
    through_a=3, count_a=2, through_b=9, count_b=3, count_c=4
)
SORCERER_CANTRIPS_BY_LEVEL: dict[int, int] = _tiered_cantrips_by_level(
    through_a=2, count_a=4, through_b=9, count_b=5, count_c=6
)

# Ensorceleur — sorts connus niv. 1+ (SRD : +1 aux paliers impairs sauf 19→20)
SORCERER_SPELLS_KNOWN_BY_LEVEL: dict[int, int] = {
    1: 2,
    2: 3,
    3: 4,
    4: 5,
    5: 6,
    6: 7,
    7: 8,
    8: 9,
    9: 10,
    10: 11,
    11: 12,
    12: 12,
    13: 13,
    14: 13,
    15: 14,
    16: 14,
    17: 15,
    18: 15,
    19: 15,
    20: 15,
}

# Magicien — grimoire (SRD : 6 + 2 × (niv − 1))
WIZARD_SPELLBOOK_BY_LEVEL: dict[int, int] = {
    level: wizard_spellbook_capacity_at_level(level) for level in range(1, 21)
}

# Hors périmètre Lot A1 — demi-lanceurs / occultiste / barde (niv. 1–3 curated)
BARD_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 2, 2: 2, 3: 2}
BARD_SPELLS_KNOWN_BY_LEVEL: dict[int, int] = {1: 4, 2: 5, 3: 6}

WARLOCK_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 2, 2: 2, 3: 2}
WARLOCK_SPELLS_KNOWN_BY_LEVEL: dict[int, int] = {1: 2, 2: 3, 3: 4}

RANGER_PREPARED_BY_LEVEL: dict[int, int] = {2: 2, 3: 3}

# Paladin : demi-lanceur préparateur (SRD 2014).


class SpellcastingFamily(str, Enum):
    KNOWN_FIXED = "known_fixed"
    PREPARED = "prepared"
    WIZARD_HYBRID = "wizard_hybrid"


KNOWN_FIXED_CLASSES: frozenset[str] = frozenset(
    {"bard", "sorcerer", "warlock"}
)
PREPARED_CLASSES: frozenset[str] = frozenset(
    {"cleric", "druid", "ranger", "paladin"}
)
WIZARD_HYBRID_CLASSES: frozenset[str] = frozenset({"wizard"})

SPELLCASTING_FAMILY_BY_CLASS: dict[str, SpellcastingFamily] = {
    "bard": SpellcastingFamily.KNOWN_FIXED,
    "sorcerer": SpellcastingFamily.KNOWN_FIXED,
    "warlock": SpellcastingFamily.KNOWN_FIXED,
    "cleric": SpellcastingFamily.PREPARED,
    "druid": SpellcastingFamily.PREPARED,
    "ranger": SpellcastingFamily.PREPARED,
    "paladin": SpellcastingFamily.PREPARED,
    "wizard": SpellcastingFamily.WIZARD_HYBRID,
}

SPELLCASTING_STATE_KEYS: dict[SpellcastingFamily, tuple[str, ...]] = {
    SpellcastingFamily.KNOWN_FIXED: (
        "cantrips_known",
        "spells_known",
        "slots_used",
    ),
    SpellcastingFamily.PREPARED: (
        "cantrips_known",
        "spells_prepared",
        "slots_used",
    ),
    SpellcastingFamily.WIZARD_HYBRID: (
        "cantrips_known",
        "spellbook",
        "spells_prepared",
        "slots_used",
    ),
}


def get_spellcasting_family(class_id: str) -> SpellcastingFamily | None:
    if class_id not in SUPPORTED_SPELLCASTING_CLASSES:
        return None
    return SPELLCASTING_FAMILY_BY_CLASS.get(class_id)


def is_known_fixed_caster(class_id: str) -> bool:
    return class_id in KNOWN_FIXED_CLASSES


def is_prepared_caster(class_id: str) -> bool:
    return class_id in PREPARED_CLASSES


def is_wizard_hybrid_caster(class_id: str) -> bool:
    return class_id in WIZARD_HYBRID_CLASSES


def casting_ability_for_class(class_id: str) -> str:
    """Caractéristique d'incantation SRD 2014 (ids ability_scores)."""
    if class_id in ("bard", "sorcerer", "warlock", "paladin"):
        return "cha"
    if class_id == "wizard":
        return "int"
    return "wis"


def cleric_prepared_capacity(wis_mod: int, level: int) -> int:
    return max(1, wis_mod + level)


def druid_prepared_capacity(wis_mod: int, level: int) -> int:
    return max(1, wis_mod + level)


def paladin_prepared_capacity(cha_mod: int, level: int) -> int:
    """SRD 2014 : mod CHA + ⌊niv/2⌋ (minimum 1)."""
    return max(1, cha_mod + level // 2)


def ranger_prepared_capacity(level: int) -> int:
    """Quota sorts préparés rôdeur (niv. 2+). Niv. 1 : 0 (visibilité gérée à part)."""
    return RANGER_PREPARED_BY_LEVEL.get(level, 0)


def wizard_prepared_capacity(int_mod: int, level: int) -> int:
    return max(1, int_mod + level)


def prepared_capacity_for_class(class_id: str, ability_mod: int, level: int) -> int:
    if class_id == "paladin":
        return paladin_prepared_capacity(ability_mod, level)
    if class_id == "ranger":
        return ranger_prepared_capacity(level)
    if class_id in ("cleric", "druid"):
        return max(1, ability_mod + level)
    if class_id == "wizard":
        return wizard_prepared_capacity(ability_mod, level)
    return 0


def cantrips_known_capacity(class_id: str, level: int) -> int:
    tables: dict[str, dict[int, int]] = {
        "bard": BARD_CANTRIPS_BY_LEVEL,
        "cleric": CLERIC_CANTRIPS_BY_LEVEL,
        "sorcerer": SORCERER_CANTRIPS_BY_LEVEL,
        "warlock": WARLOCK_CANTRIPS_BY_LEVEL,
        "druid": DRUID_CANTRIPS_BY_LEVEL,
        "wizard": WIZARD_CANTRIPS_BY_LEVEL,
    }
    return tables.get(class_id, {}).get(level, 0)


def spells_known_capacity(class_id: str, level: int) -> int:
    """Quota sorts niv. 1+ connus (famille KNOWN_FIXED)."""
    tables: dict[str, dict[int, int]] = {
        "bard": BARD_SPELLS_KNOWN_BY_LEVEL,
        "sorcerer": SORCERER_SPELLS_KNOWN_BY_LEVEL,
        "warlock": WARLOCK_SPELLS_KNOWN_BY_LEVEL,
    }
    return tables.get(class_id, {}).get(level, 0)


# Alias rétrocompat tests P0
RANGER_SPELLS_KNOWN_BY_LEVEL = RANGER_PREPARED_BY_LEVEL


def spellbook_capacity(class_id: str, level: int) -> int:
    if class_id == "wizard":
        return wizard_spellbook_capacity_at_level(level)
    return 0
