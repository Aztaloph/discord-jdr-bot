# tests/unit/test_level_up_cap5.py
"""Sous-lot 2 / Lot A2 — montée mécanique niv. 4–20 (slots SRD, maîtrise, cap)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_progression import (
    MAX_CHARACTER_LEVEL,
    LevelUpError,
    apply_level_up,
)
from jdr_engine.rules.spellcasting.cast import get_spellcasting_stats
from jdr_engine.rules.spellcasting.slots import FULL_CASTER_SPELL_SLOTS, get_max_spell_slots
from jdr_engine.rules.spellcasting.stats import spell_attack_bonus, spell_save_dc

from tests.helpers.level_up import wizard_at_level


class TestFullCasterSlotTable(unittest.TestCase):
    def test_table_covers_levels_1_to_20(self):
        self.assertEqual(set(FULL_CASTER_SPELL_SLOTS.keys()), set(range(1, 21)))

    def test_wizard_slots_level_4_and_5(self):
        self.assertEqual(get_max_spell_slots("wizard", 4), {1: 4, 2: 3})
        self.assertEqual(get_max_spell_slots("wizard", 5), {1: 4, 2: 3, 3: 2})


class TestLevelUpCapFive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def _wizard_to_level(self, target: int):
        return wizard_at_level(self.engine, target)

    def test_max_character_level_constant(self):
        self.assertEqual(MAX_CHARACTER_LEVEL, 20)

    def test_spellcasting_stats_level_5(self):
        char = self._wizard_to_level(5)
        prof = self.engine.get_proficiency_bonus(5)
        self.assertEqual(prof, 3)
        mod, attack, dc = get_spellcasting_stats(char, self.engine)
        self.assertEqual(dc, spell_save_dc(prof, mod))
        self.assertEqual(attack, spell_attack_bonus(prof, mod))
        self.assertEqual(dc, 8 + 3 + mod)

    def test_level_up_4_to_5_proficiency_in_dd_and_attack(self):
        char = self._wizard_to_level(4)
        mod4, attack4, dc4 = get_spellcasting_stats(char, self.engine)
        self.assertEqual(self.engine.get_proficiency_bonus(4), 2)
        self.assertEqual(dc4, 8 + 2 + mod4)
        self.assertEqual(attack4, 2 + mod4)

        char, result = apply_level_up(char, self.engine)
        self.assertEqual(result.old_level, 4)
        self.assertEqual(result.new_level, 5)

        mod5, attack5, dc5 = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod5, mod4)
        self.assertEqual(self.engine.get_proficiency_bonus(5), 3)
        self.assertEqual(dc5, dc4 + 1)
        self.assertEqual(attack5, attack4 + 1)
        self.assertEqual(get_max_spell_slots("wizard", 5), {1: 4, 2: 3, 3: 2})

    def test_level_20_cannot_level_up_again(self):
        char = self._wizard_to_level(20)
        with self.assertRaises(LevelUpError):
            apply_level_up(char, self.engine)


if __name__ == "__main__":
    unittest.main(verbosity=2)
