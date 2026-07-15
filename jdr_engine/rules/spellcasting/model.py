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

# ── Quotas SRD 2014 (niveaux de personnage 1–3, catalogue curated) ───────────

BARD_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 2, 2: 2, 3: 2}
BARD_SPELLS_KNOWN_BY_LEVEL: dict[int, int] = {1: 4, 2: 5, 3: 6}

CLERIC_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 3, 2: 3, 3: 3}

SORCERER_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 4, 2: 4, 3: 5}
SORCERER_SPELLS_KNOWN_BY_LEVEL: dict[int, int] = {1: 2, 2: 3, 3: 4}

WARLOCK_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 2, 2: 2, 3: 2}
WARLOCK_SPELLS_KNOWN_BY_LEVEL: dict[int, int] = {1: 2, 2: 3, 3: 4}

DRUID_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 2, 2: 2, 3: 2}

WIZARD_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 3, 2: 3, 3: 4}
WIZARD_SPELLBOOK_BY_LEVEL: dict[int, int] = {1: 6, 2: 8, 3: 10}

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
        return WIZARD_SPELLBOOK_BY_LEVEL.get(level, 6)
    return 0
