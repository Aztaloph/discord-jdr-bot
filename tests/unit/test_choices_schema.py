# tests/unit/test_choices_schema.py
"""Schéma choices — normalisation et rétrocompatibilité."""
from __future__ import annotations

import unittest

from jdr_engine.domain.character.choices_schema import (
    get_fighting_style_id,
    get_skill_choices,
    get_specialization_id,
    normalize_character_choices,
)


class TestChoicesSchema(unittest.TestCase):
    def test_empty_choices(self):
        self.assertEqual(normalize_character_choices(None), {})
        self.assertEqual(normalize_character_choices({}), {})

    def test_legacy_aliases_merged(self):
        raw = {
            "skill_proficiencies": ["stealth", "perception"],
            "subclass": "champion",
            "fighting_style": "archery",
        }
        normalized = normalize_character_choices(raw)
        self.assertEqual(normalized["skills"], ["stealth", "perception"])
        self.assertNotIn("skill_proficiencies", normalized)
        self.assertEqual(normalized["specialization"], "champion")
        self.assertNotIn("subclass", normalized)
        self.assertEqual(normalized["fighting_style"], "archery")

    def test_specialization_dict_form(self):
        normalized = normalize_character_choices({"specialization": {"id": "life"}})
        self.assertEqual(get_specialization_id(normalized), "life")

    def test_preserves_unknown_keys(self):
        normalized = normalize_character_choices(
            {"spellcasting": {"cantrips_known": []}, "custom_future": True}
        )
        self.assertIn("spellcasting", normalized)
        self.assertTrue(normalized.get("custom_future"))

    def test_accessors(self):
        choices = normalize_character_choices(
            {
                "skills": ["arcana"],
                "fighting_style": "dueling",
            }
        )
        self.assertEqual(get_skill_choices(choices), ("arcana",))
        self.assertEqual(get_fighting_style_id(choices), "dueling")


if __name__ == "__main__":
    unittest.main(verbosity=2)
