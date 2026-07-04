# tests/unit/test_derived_stats.py
"""Calculs dérivés SRD — Lot 0 fondations."""
from __future__ import annotations

import unittest

from jdr_engine.domain.character import AbilityScores, Character
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.derived_stats import (
    calculate_armor_class,
    calculate_initiative,
    calculate_saving_throw_modifier,
    collect_proficient_skills,
    read_hit_dice,
)


class TestDerivedStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_initiative_equals_dex_mod(self):
        self.assertEqual(calculate_initiative(3), 3)
        self.assertEqual(calculate_initiative(-1), -1)

    def test_saving_throw_proficiency(self):
        self.assertEqual(
            calculate_saving_throw_modifier(2, proficient=True, proficiency_bonus=2),
            4,
        )
        self.assertEqual(
            calculate_saving_throw_modifier(2, proficient=False, proficiency_bonus=2),
            2,
        )

    def test_barbarian_unarmored_ac(self):
        char = Character(
            owner_id="1",
            name="Grog",
            race_id="human",
            class_id="barbarian",
            level=1,
            ability_scores=AbilityScores.from_dict(
                {"str": 15, "dex": 14, "con": 15, "int": 8, "wis": 10, "cha": 8}
            ),
        )
        sheet = build_character_sheet(char, self.engine)
        # humain +1 → DEX 15 (+2), CON 16 (+3) → CA 10+2+3=15
        self.assertEqual(sheet.ac, 15)

    def test_fighter_default_ac(self):
        char = Character(
            owner_id="1",
            name="Tank",
            race_id="human",
            class_id="fighter",
            level=1,
            ability_scores=AbilityScores.from_dict(
                dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)
            ),
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(sheet.ac, 10)  # DEX 11 (+1 humain) → mod +0

    def test_saving_throws_on_sheet(self):
        char = Character(
            owner_id="1",
            name="Clerc",
            race_id="human",
            class_id="cleric",
            level=1,
            ability_scores=AbilityScores.from_dict(
                dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)
            ),
        )
        sheet = build_character_sheet(char, self.engine)
        joined = " ".join(sheet.saving_throws)
        self.assertIn("SAG", joined)
        self.assertIn("CHA", joined)
        self.assertIn("●", joined)

    def test_skills_from_choices_and_race(self):
        char = Character(
            owner_id="1",
            name="Elf",
            race_id="elf",
            class_id="rogue",
            level=1,
            ability_scores=AbilityScores.from_dict(
                dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)
            ),
            choices={"skills": ["stealth"]},
        )
        skills = collect_proficient_skills(char, self.engine)
        self.assertIn("stealth", skills)
        self.assertIn("perception", skills)  # keen_senses elfe

    def test_hit_dice_read_only_defaults(self):
        char = Character(
            owner_id="1",
            name="New",
            race_id="human",
            class_id="wizard",
            level=2,
            ability_scores=AbilityScores.from_dict(
                dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)
            ),
        )
        remaining, total = read_hit_dice(char)
        self.assertEqual(total, 2)
        self.assertEqual(remaining, 2)

    def test_specialization_on_sheet(self):
        char = Character(
            owner_id="1",
            name="Champ",
            race_id="human",
            class_id="fighter",
            level=3,
            ability_scores=AbilityScores.from_dict(
                dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)
            ),
            choices={"specialization": "champion", "fighting_style": "archery"},
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(sheet.specialization_id, "champion")
        self.assertIn("Champion", sheet.class_display)
        self.assertEqual(sheet.fighting_style_id, "archery")


if __name__ == "__main__":
    unittest.main(verbosity=2)
