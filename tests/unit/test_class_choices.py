# tests/unit/test_class_choices.py
"""Choix de création niv. 1 — compétences et domaine clerc."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.class_choices import (
    CreationChoiceError,
    get_cleric_domain_options,
    get_skill_choice_config,
    validate_cleric_domain,
    validate_skill_choices,
)
from jdr_engine.rules.character_creation.finalize import (
    finalize_new_character,
    has_playable_subclass,
)


class TestClassChoices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_wizard_skill_config(self):
        config = get_skill_choice_config(self.engine, "wizard")
        assert config is not None
        self.assertEqual(config.count, 2)
        self.assertIn("arcana", config.options)

    def test_validate_wizard_skills(self):
        result = validate_skill_choices(
            self.engine, "wizard", ["arcana", "history"]
        )
        self.assertEqual(result, ("arcana", "history"))

    def test_reject_wrong_skill_count(self):
        with self.assertRaises(CreationChoiceError):
            validate_skill_choices(self.engine, "wizard", ["arcana"])

    def test_cleric_domain_options(self):
        self.assertIn("life", get_cleric_domain_options(self.engine))

    def test_cleric_requires_domain(self):
        self.assertTrue(has_playable_subclass("cleric", self.engine))
        with self.assertRaises(CreationChoiceError):
            validate_cleric_domain(self.engine, "cleric", None)
        self.assertEqual(
            validate_cleric_domain(self.engine, "cleric", "life"),
            "life",
        )

    def test_finalize_wizard_with_skills(self):
        scores = dict.fromkeys(
            ("str", "dex", "con", "int", "wis", "cha"), 8
        )
        scores["int"] = 15
        scores["con"] = 14
        char = finalize_new_character(
            name="Mage",
            race_id="human",
            class_id="wizard",
            owner_id="1",
            guild_id="100",
            base_scores=scores,
            engine=self.engine,
            skills=["arcana", "investigation"],
        )
        self.assertEqual(char.choices["skills"], ["arcana", "investigation"])
        self.assertIn("fire_bolt", char.choices["spellcasting"]["cantrips_known"])
        self.assertNotIn(
            "scorching_ray", char.choices["spellcasting"]["spells_prepared"]
        )

    def test_finalize_cleric_with_domain(self):
        scores = dict.fromkeys(
            ("str", "dex", "con", "int", "wis", "cha"), 8
        )
        scores["wis"] = 15
        char = finalize_new_character(
            name="Clerc",
            race_id="human",
            class_id="cleric",
            owner_id="1",
            guild_id="100",
            base_scores=scores,
            engine=self.engine,
            skills=["medicine", "religion"],
            specialization="life",
        )
        self.assertEqual(char.choices["specialization"], "life")
        self.assertIn("sacred_flame", char.choices["spellcasting"]["cantrips_known"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
