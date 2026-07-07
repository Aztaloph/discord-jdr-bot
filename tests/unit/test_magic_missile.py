# tests/unit/test_magic_missile.py
"""Projectile magique — auto-hit et dégâts multi-dards (Lot B fix)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.spellcasting.cast import cast_spell
from jdr_engine.rules.spellcasting.state import get_spells_prepared_list
from tests.helpers.creation import wizard_creation_kwargs


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestMagicMissile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _wizard_with_magic_missile(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        prepared = list(get_spells_prepared_list(char))
        if "magic_missile" not in prepared:
            char.choices["spellcasting"]["spells_prepared"] = prepared + [
                "magic_missile"
            ]
        return char

    def test_level_1_auto_hit_three_darts(self):
        char = self._wizard_with_magic_missile()
        rng = SequenceRng([2, 3, 4])  # 1d4 → +1 → 3, 4, 5
        result = cast_spell(
            char, "magic_missile", self.engine, rng=rng, persist_slots=False
        )
        self.assertIsNone(result.attack_bonus)
        self.assertEqual(len(result.attack_rolls), 3)
        self.assertTrue(all(atk.auto_hit for atk in result.attack_rolls))
        self.assertTrue(all(atk.d20_result is None for atk in result.attack_rolls))
        self.assertEqual(
            [atk.damage_total for atk in result.attack_rolls],
            [3, 4, 5],
        )
        self.assertEqual(result.damage_total, 12)
        self.assertIn("3×(1d4+1)", result.damage_notation or "")
        joined = "\n".join(result.display_lines)
        self.assertIn("Touché automatiquement", joined)
        self.assertNotIn("Jet d'attaque de sort", joined)
        self.assertIn("Dard 1", joined)
        self.assertIn("Dard 3", joined)

    def test_upcast_level_2_slot_four_darts(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=3),
        )
        prepared = list(get_spells_prepared_list(char))
        if "magic_missile" not in prepared:
            char.choices["spellcasting"]["spells_prepared"] = prepared + [
                "magic_missile"
            ]
        char.choices["spellcasting"]["slots_used"] = {"1": 4}
        rng = SequenceRng([1, 2, 3, 4])
        result = cast_spell(
            char, "magic_missile", self.engine, rng=rng, persist_slots=False
        )
        self.assertEqual(len(result.attack_rolls), 4)
        self.assertEqual(result.damage_total, 14)  # (1+1)+(2+1)+(3+1)+(4+1)
        self.assertEqual(result.slot_consumed_level, 2)

    def test_burning_hands_save_unchanged(self):
        char = self._wizard_with_magic_missile()
        prepared = list(get_spells_prepared_list(char))
        if "burning_hands" not in prepared:
            char.choices["spellcasting"]["spells_prepared"] = prepared + [
                "burning_hands"
            ]
        rng = SequenceRng([4, 4, 4])
        result = cast_spell(
            char, "burning_hands", self.engine, rng=rng, persist_slots=False
        )
        self.assertEqual(result.effect_type, "saving_throw")
        self.assertIsNotNone(result.save_dc)
        self.assertEqual(result.damage_total, 12)

    def test_hellish_rebuke_unchanged(self):
        char = self._wizard_with_magic_missile()
        prepared = list(get_spells_prepared_list(char))
        if "hellish_rebuke" not in prepared:
            char.choices["spellcasting"]["spells_prepared"] = prepared + [
                "hellish_rebuke"
            ]
        rng = SequenceRng([5, 5])
        result = cast_spell(
            char, "hellish_rebuke", self.engine, rng=rng, persist_slots=False
        )
        self.assertEqual(result.effect_type, "saving_throw")
        self.assertEqual(result.damage_total, 10)

    def test_inflict_wounds_attack_unchanged(self):
        char = self._wizard_with_magic_missile()
        prepared = list(get_spells_prepared_list(char))
        if "inflict_wounds" not in prepared:
            char.choices["spellcasting"]["spells_prepared"] = prepared + [
                "inflict_wounds"
            ]
        rng = SequenceRng([15, 5, 5, 5])
        result = cast_spell(
            char, "inflict_wounds", self.engine, rng=rng, persist_slots=False
        )
        self.assertIsNotNone(result.attack_bonus)
        self.assertEqual(len(result.attack_rolls), 1)
        self.assertIsNotNone(result.attack_rolls[0].d20_result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
