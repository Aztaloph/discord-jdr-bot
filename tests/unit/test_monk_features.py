# tests/unit/test_monk_features.py
"""Moine — features SRD 2014 niv. 1-3 (Phase 4.7 Lot A)."""
from __future__ import annotations

import unittest

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.class_features.monk import (
    deflect_missiles_can_throw,
    ki_max,
    ki_options,
    martial_arts_die,
    unarmored_movement_bonus,
)


class TestMonkMechanics(unittest.TestCase):
    def test_martial_arts_die_level_1_3(self):
        self.assertEqual(martial_arts_die(1), 4)
        self.assertEqual(martial_arts_die(3), 4)

    def test_ki_max_by_level(self):
        self.assertEqual(ki_max(1), 0)
        self.assertEqual(ki_max(2), 2)
        self.assertEqual(ki_max(3), 3)

    def test_ki_options_level_2(self):
        self.assertEqual(ki_options(1), frozenset())
        self.assertEqual(
            ki_options(2),
            frozenset({"flurry_of_blows", "patient_defense", "step_of_the_wind"}),
        )

    def test_unarmored_movement(self):
        self.assertEqual(unarmored_movement_bonus(1), 0)
        self.assertEqual(unarmored_movement_bonus(2), 10)

    def test_deflect_missiles_throw(self):
        self.assertTrue(deflect_missiles_can_throw(3, True, 2))
        self.assertFalse(deflect_missiles_can_throw(2, True, 2))
        self.assertFalse(deflect_missiles_can_throw(3, False, 2))
        self.assertFalse(deflect_missiles_can_throw(3, True, 0))


class TestMonkFeaturesByLevel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_level_1_features(self):
        ids = {t.entry_id for t in self.engine.get_class_features("monk", 1)}
        self.assertEqual(ids, {"unarmored_defense_monk", "martial_arts"})

    def test_level_3_includes_deflect_missiles(self):
        ids = {t.entry_id for t in self.engine.get_class_features("monk", 3)}
        self.assertIn("deflect_missiles", ids)
        self.assertIn("monastic_tradition", ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
