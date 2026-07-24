# jdr_engine/rules/progression_constants.py
"""Plafonds de progression — module racine pour éviter imports circulaires."""

MAX_CHARACTER_LEVEL = 5
MAX_LEVEL_LOT2 = MAX_CHARACTER_LEVEL  # deprecated

# Full casters SRD 2014 — faces du dé de vie (HP = +1 DV/niv., type selon classe)
FULL_CASTER_HIT_DIE_FACES: dict[str, int] = {
    "wizard": 6,
    "sorcerer": 6,
    "cleric": 8,
    "druid": 8,
}
