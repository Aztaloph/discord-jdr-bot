# jdr_engine/rules/character_creation/playable.py
"""Périmètre jouable — classes / races SRD 2014."""

# 12 classes SRD — sélectionnables à la création (Lot 0).
SRD_CLASSES: tuple[str, ...] = (
    "barbarian",
    "bard",
    "cleric",
    "druid",
    "fighter",
    "monk",
    "paladin",
    "ranger",
    "rogue",
    "sorcerer",
    "warlock",
    "wizard",
)

PLAYABLE_CLASSES: tuple[str, ...] = SRD_CLASSES

# Montée de niveau — classes Lot 1–2 (niv. 2–3 + sous-classe niv. 3).
LEVEL_UP_CLASSES: tuple[str, ...] = (
    "wizard",
    "cleric",
    "fighter",
    "barbarian",
    "rogue",
    "monk",
    "ranger",
    "paladin",
    "bard",
    "sorcerer",
    "druid",
    "warlock",
)

PLAYABLE_RACES: tuple[str, ...] = (
    "human",
    "elf",
    "dwarf",
    "halfling",
    "dragonborn",
    "gnome",
    "half_elf",
    "half_orc",
    "tiefling",
)
