# jdr_engine/rules/character_creation/playable.py
"""Périmètre jouable actuel — classes / races réellement supportées."""

PLAYABLE_CLASSES: tuple[str, ...] = ("wizard", "cleric")

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
