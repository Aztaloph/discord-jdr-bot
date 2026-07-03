# jdr_engine/rules/spellcasting/__init__.py
"""Lanceur de sorts SRD 5.1 2014 — Lot B Magicien niv. 1-3."""
from jdr_engine.rules.spellcasting.slots import (
    WIZARD_SPELL_SLOTS,
    get_max_spell_slots,
    get_remaining_slots,
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

__all__ = [
    "WIZARD_SPELL_SLOTS",
    "consume_spell_slot",
    "get_max_spell_slots",
    "get_remaining_slots",
    "get_spellcasting_state",
    "reset_spell_slots",
    "spell_attack_bonus",
    "spell_save_dc",
]
