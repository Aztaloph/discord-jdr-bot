# tests/unit/test_lot2_martial.py
"""Lot 2 — Roublard & Moine SRD 2014 (niv. 1–3, sous-classes)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, roll_d20
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import LevelUpPendingChoice, apply_level_up
from jdr_engine.rules.class_features.monk import (
    ki_points_max,
    ki_points_remaining,
    martial_arts_die,
    unarmored_movement_bonus,
)
from jdr_engine.rules.class_features.rogue import sneak_attack_dice_count
from jdr_engine.rules.roll_effects import collect_roll_effects, enrich_roll_request
from tests.helpers.creation import (
    barbarian_creation_kwargs,
    monk_creation_kwargs,
    rogue_creation_kwargs,
    wizard_creation_kwargs,
)


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestLot2Rogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_expertise_doubles_proficiency_on_sheet(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Shadow",
            engine=self.engine,
            **rogue_creation_kwargs(
                expertise_skills=["stealth", "perception"],
            ),
        )
        effects = collect_roll_effects(char, self.engine)
        req = enrich_roll_request(
            D20RollRequest(
                roll_type="ability_check",
                skill="stealth",
                ability="dex",
                ability_modifier=2,
                proficiency_bonus=2,
                is_proficient=True,
            ),
            char,
        )
        result = roll_d20(D20RollContext(req, effects), rng=SequenceRng([10]))
        self.assertEqual(result.modifier, 6)
        sheet = build_character_sheet(char, self.engine)
        self.assertTrue(any("Expertise" in line for line in sheet.class_features_lines))

    def test_sneak_attack_progression(self):
        char1 = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="R1",
            engine=self.engine,
            **rogue_creation_kwargs(level=1),
        )
        self.assertEqual(sneak_attack_dice_count(1), 1)
        sheet1 = build_character_sheet(char1, self.engine)
        self.assertTrue(any("1d6" in line for line in sheet1.class_features_lines))

        char3 = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="R3",
            engine=self.engine,
            **rogue_creation_kwargs(level=3, specialization="thief"),
        )
        self.assertEqual(sneak_attack_dice_count(3), 2)
        sheet3 = build_character_sheet(char3, self.engine)
        self.assertIn("Voleur", sheet3.class_display)
        self.assertTrue(any("Mains lestes" in line for line in sheet3.class_features_lines))

    def test_level_up_to_3_thief(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Rogue",
            engine=self.engine,
            **rogue_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        with self.assertRaises(LevelUpPendingChoice):
            apply_level_up(char, self.engine)
        char, result = apply_level_up(char, self.engine, subclass="thief")
        self.assertEqual(result.new_level, 3)
        self.assertEqual(char.choices["specialization"], "thief")


class TestLot2Monk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_unarmored_defense_and_speed(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Monk",
            engine=self.engine,
            **monk_creation_kwargs(level=2),
        )
        sheet = build_character_sheet(char, self.engine)
        # DEX 15+1 humain (+3), WIS 14+1 (+2) → CA 15
        self.assertEqual(sheet.ac, 15)
        self.assertEqual(sheet.speed, 40)
        self.assertEqual(unarmored_movement_bonus(2), 10)

    def test_ki_counter_level_3(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Monk",
            engine=self.engine,
            **monk_creation_kwargs(level=3, specialization="open_hand"),
        )
        self.assertEqual(ki_points_max(3), 3)
        self.assertEqual(ki_points_remaining(char.choices, level=3), 3)
        sheet = build_character_sheet(char, self.engine)
        self.assertTrue(any("Ki" in line and "3/3" in line for line in sheet.class_features_lines))
        self.assertTrue(any("Main ouverte" in line for line in sheet.class_features_lines))

    def test_martial_arts_die_display(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Monk",
            engine=self.engine,
            **monk_creation_kwargs(level=1),
        )
        self.assertEqual(martial_arts_die(1), 4)
        sheet = build_character_sheet(char, self.engine)
        self.assertTrue(any("d4" in line for line in sheet.class_features_lines))

    def test_level_up_open_hand_pending(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Monk",
            engine=self.engine,
            **monk_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        self.assertEqual(ki_points_remaining(char.choices, level=2), 2)
        with self.assertRaises(LevelUpPendingChoice):
            apply_level_up(char, self.engine)
        char, _ = apply_level_up(char, self.engine, subclass="open_hand")
        self.assertEqual(char.choices["specialization"], "open_hand")


class TestLot2NonRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_fighter_lot1_still_works(self):
        from tests.helpers.creation import fighter_creation_kwargs

        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="F",
            engine=self.engine,
            **fighter_creation_kwargs(),
        )
        self.assertEqual(char.choices["fighting_style"], "defense")

    def test_barbarian_lot1_still_works(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="B",
            engine=self.engine,
            **barbarian_creation_kwargs(level=1),
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(sheet.ac, 12)

    def test_wizard_still_works(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="W",
            engine=self.engine,
            **wizard_creation_kwargs(),
        )
        self.assertIn("fire_bolt", char.choices["spellcasting"]["cantrips_known"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
