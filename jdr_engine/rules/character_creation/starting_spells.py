# jdr_engine/rules/character_creation/starting_spells.py
"""Sorts de départ minimaux (niv. 1) — testables via /sort, catalogue Lot B."""

from __future__ import annotations

from jdr_engine.rules.spellcasting.spells_catalog import SUPPORTED_SPELLCASTING_CLASSES

# Magicien niv. 1 : 1 tour de magie + 3 sorts niv. 1 (grimoire initial réduit)
WIZARD_STARTING_CANTRIPS: tuple[str, ...] = ("fire_bolt",)
WIZARD_STARTING_SPELLS: tuple[str, ...] = (
    "chromatic_orb",
    "burning_hands",
    "detect_magic",
)

# Clerc niv. 1 : 1 tour de magie + 3 sorts niv. 1 (tous connus ; préparation = Lot ultérieur)
CLERIC_STARTING_CANTRIPS: tuple[str, ...] = ("sacred_flame",)
CLERIC_STARTING_SPELLS: tuple[str, ...] = (
    "cure_wounds",
    "bless",
    "inflict_wounds",
)

_STARTING_BY_CLASS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "wizard": (WIZARD_STARTING_CANTRIPS, WIZARD_STARTING_SPELLS),
    "cleric": (CLERIC_STARTING_CANTRIPS, CLERIC_STARTING_SPELLS),
}


def build_starting_spellcasting(class_id: str) -> dict:
    """
    État spellcasting initial — sorts connus uniquement (préparation future).

    ``spells_prepared`` contient provisoirement tous les sorts connus niv. 1+.
    """
    if class_id not in SUPPORTED_SPELLCASTING_CLASSES:
        return {}
    cantrips, spells = _STARTING_BY_CLASS.get(class_id, ((), ()))
    prepared = list(spells)
    return {
        "cantrips_known": list(cantrips),
        "spells_prepared": prepared,
        "slots_used": {},
    }
