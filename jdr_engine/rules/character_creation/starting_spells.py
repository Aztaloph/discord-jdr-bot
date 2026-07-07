# jdr_engine/rules/character_creation/starting_spells.py
"""Réexport — implémentation dans ``jdr_engine.rules.spellcasting.starting_spells``."""

from jdr_engine.rules.spellcasting.starting_spells import (
    build_starting_spellcasting,
    init_half_caster_spellcasting_if_needed,
    upgrade_full_caster_spellcasting,
    upgrade_half_caster_spellcasting,
    upgrade_pact_caster_spellcasting,
)

__all__ = [
    "build_starting_spellcasting",
    "init_half_caster_spellcasting_if_needed",
    "upgrade_full_caster_spellcasting",
    "upgrade_half_caster_spellcasting",
    "upgrade_pact_caster_spellcasting",
]
