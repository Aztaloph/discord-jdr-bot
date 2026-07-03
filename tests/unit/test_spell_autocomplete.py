# tests/unit/test_spell_autocomplete.py
"""Autocomplétion /sort — 5 sorts Lot B globaux."""
from __future__ import annotations

import unittest

from jdr_engine.rules import RuleEngine
from interfaces.discord.handlers.spell import build_lot_b_spell_autocomplete_choices


class TestSpellAutocomplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_all_ten_spells_when_empty_query(self):
        choices = build_lot_b_spell_autocomplete_choices(self.engine, "")
        self.assertEqual(len(choices), 10)

    def test_all_five_wizard_spells_when_empty_query(self):
        from interfaces.discord.handlers.spell import build_spell_autocomplete_choices

        choices = build_spell_autocomplete_choices(self.engine, "", class_id="wizard")
        self.assertEqual(len(choices), 5)

    def test_partial_fire_matches_fire_bolt(self):
        choices = build_lot_b_spell_autocomplete_choices(self.engine, "fire")
        values = [c.value for c in choices]
        self.assertIn("fire_bolt", values)

    def test_partial_id_fire_bolt(self):
        choices = build_lot_b_spell_autocomplete_choices(self.engine, "fire_bolt")
        values = [c.value for c in choices]
        self.assertEqual(values, ["fire_bolt"])

    def test_french_label_trait(self):
        choices = build_lot_b_spell_autocomplete_choices(self.engine, "trait")
        values = [c.value for c in choices]
        self.assertIn("fire_bolt", values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
