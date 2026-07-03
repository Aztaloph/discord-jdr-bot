# jdr_engine/rules/spellcasting/__init__.py
"""Lanceur de sorts SRD 5.1 2014 — Magicien & Clerc niv. 1-3."""
from jdr_engine.rules.spellcasting.cast import SpellCastError, SpellCastResult, cast_spell
from jdr_engine.rules.spellcasting.slots import (
    FULL_CASTER_SPELL_SLOTS,
    get_max_spell_slots,
    get_remaining_slots,
)
from jdr_engine.rules.spellcasting.spells_catalog import (
    CLERIC_SPELL_IDS,
    SUPPORTED_SPELLCASTING_CLASSES,
    WIZARD_SPELL_IDS,
    all_spellcasting_spell_ids,
    get_spell_ids_for_class,
)
from jdr_engine.rules.spellcasting.state import (
    consume_spell_slot,
    get_spellcasting_state,
    reset_spell_slots,
)
from jdr_engine.rules.spellcasting.stats import (
    spell_attack_bonus,
    spell_save_dc,
)

# Alias rétrocompat
WIZARD_SPELL_SLOTS = FULL_CASTER_SPELL_SLOTS

__all__ = [
    "CLERIC_SPELL_IDS",
    "FULL_CASTER_SPELL_SLOTS",
    "SUPPORTED_SPELLCASTING_CLASSES",
    "SpellCastError",
    "SpellCastResult",
    "WIZARD_SPELL_IDS",
    "WIZARD_SPELL_SLOTS",
    "all_spellcasting_spell_ids",
    "cast_spell",
    "consume_spell_slot",
    "get_max_spell_slots",
    "get_remaining_slots",
    "get_spell_ids_for_class",
    "get_spellcasting_state",
    "reset_spell_slots",
    "spell_attack_bonus",
    "spell_save_dc",
]
