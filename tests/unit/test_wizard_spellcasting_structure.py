# tests/unit/test_wizard_spellcasting_structure.py
"""Magicien — structure lanceur de sorts (Lot B, étape 1)."""
from __future__ import annotations

import unittest

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.spellcasting import (
    get_max_spell_slots,
    get_remaining_slots,
    spell_attack_bonus,
    spell_save_dc,
)
from jdr_engine.rules.spellcasting.state import (
    consume_spell_slot,
    get_slots_used,
    reset_spell_slots,
)


def _wizard(level: int = 1, *, slots_used: dict[int, int] | None = None) -> Character:
    return Character(
        owner_id="1",
        name="Merlin",
        race_id="human",
        class_id="wizard",
        level=level,
        ability_scores=AbilityScores(),
        choices={
            "spellcasting": {
                "cantrips_known": ["fire_bolt"],
                "spells_prepared": ["burning_hands"],
                "slots_used": {str(k): v for k, v in (slots_used or {}).items()},
            }
        },
    )


class TestWizardSpellStats(unittest.TestCase):
    def test_spell_save_dc_srd(self):
        self.assertEqual(spell_save_dc(2, 3), 13)

    def test_spell_attack_bonus_srd(self):
        self.assertEqual(spell_attack_bonus(2, 3), 5)


class TestWizardSpellSlots(unittest.TestCase):
    def test_max_slots_level_1_to_3(self):
        self.assertEqual(get_max_spell_slots("wizard", 1), {1: 2})
        self.assertEqual(get_max_spell_slots("wizard", 2), {1: 3})
        self.assertEqual(get_max_spell_slots("wizard", 3), {1: 4, 2: 2})

    def test_consume_slot_level_1(self):
        char = _wizard(1)
        updated = consume_spell_slot(char, 1)
        self.assertEqual(get_slots_used(updated), {1: 1})
        self.assertEqual(get_remaining_slots("wizard", 1, get_slots_used(updated)), {1: 1})

    def test_consume_higher_slot_when_lower_empty(self):
        char = _wizard(3, slots_used={1: 4})
        updated = consume_spell_slot(char, 1)
        self.assertEqual(get_slots_used(updated), {1: 4, 2: 1})

    def test_reset_slots(self):
        char = _wizard(2, slots_used={1: 2})
        reset = reset_spell_slots(char)
        self.assertEqual(get_slots_used(reset), {})
