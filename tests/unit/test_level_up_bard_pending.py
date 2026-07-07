# tests/unit/test_level_up_bard_pending.py
"""Montée de niveau barde niv.3 — flux pending compétences (Fix Lot 4)."""
from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import LevelUpPendingChoice, apply_level_up
from tests.helpers.creation import bard_creation_kwargs, cleric_creation_kwargs


class TestBardLevelUpPendingFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _bard_level_2(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Melody",
            engine=self.engine,
            **bard_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        return char

    def test_level_2_no_pending_choice(self):
        char = self._bard_level_2()
        self.assertEqual(char.level, 2)

    def test_level_3_subclass_then_lore_then_expertise(self):
        char = self._bard_level_2()

        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        self.assertEqual(ctx.exception.pending.choice_type, "subclass")

        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(
                char,
                self.engine,
                subclass="lore",
            )
        pending_lore = ctx.exception.pending
        self.assertEqual(pending_lore.choice_type, "lore_bonus_skills")
        self.assertEqual(pending_lore.required_count, 3)
        self.assertEqual(pending_lore.parent_subclass, "lore")
        self.assertGreaterEqual(len(pending_lore.options), 3)

        merged = replace(
            char,
            choices={
                **(char.choices or {}),
                **(pending_lore.character.choices or {}),
            },
        )
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(
                merged,
                self.engine,
                subclass="lore",
                lore_bonus_skills=["arcana", "history", "investigation"],
            )
        pending_exp = ctx.exception.pending
        self.assertEqual(pending_exp.choice_type, "expertise_skills")
        self.assertEqual(pending_exp.required_count, 2)

        merged2 = replace(
            merged,
            choices={
                **(merged.choices or {}),
                **(pending_exp.character.choices or {}),
            },
        )
        char, result = apply_level_up(
            merged2,
            self.engine,
            subclass="lore",
            lore_bonus_skills=["arcana", "history", "investigation"],
            expertise_skills=["performance", "persuasion"],
        )
        self.assertEqual(result.new_level, 3)
        self.assertEqual(char.choices.get("specialization"), "lore")
        self.assertEqual(
            char.choices.get("lore_bonus_skills"),
            ["arcana", "history", "investigation"],
        )
        self.assertEqual(
            char.choices.get("expertise_skills"),
            ["performance", "persuasion"],
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertTrue(any("Savoir" in line for line in sheet.class_features_lines))
        self.assertTrue(any("Expertise" in line for line in sheet.class_features_lines))

    def test_subclass_only_without_skills_raises_pending_not_error(self):
        char = self._bard_level_2()
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine, subclass="lore")
        self.assertEqual(ctx.exception.pending.choice_type, "lore_bonus_skills")


class TestClericLevelUpUnchanged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_cleric_1_to_3_no_skill_pending(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Marie",
            engine=self.engine,
            **cleric_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        self.assertEqual(char.level, 2)
        char, _ = apply_level_up(char, self.engine)
        self.assertEqual(char.level, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
