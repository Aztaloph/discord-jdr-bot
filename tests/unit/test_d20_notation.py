# tests/unit/test_d20_notation.py
"""Normalisation notation d20 /roll — SRD 2014 avantage = max."""
from __future__ import annotations

import unittest

from jdr_engine.dice import DiceError

from interfaces.discord.handlers.combat_roll import CombatRollFlags
from interfaces.discord.handlers.d20_notation import normalize_d20_roll_input


class TestD20NotationNormalize(unittest.TestCase):
    def test_single_d20_unchanged(self):
        n = normalize_d20_roll_input("d20+4", "normal", CombatRollFlags())
        self.assertIsNotNone(n)
        assert n is not None
        self.assertEqual(n.ability_modifier, 4)
        self.assertEqual(n.mode, "normal")

    def test_2d20_becomes_advantage(self):
        n = normalize_d20_roll_input("2d20+4", "normal", CombatRollFlags())
        assert n is not None
        self.assertEqual(n.mode, "avantage")
        self.assertTrue(n.from_double_notation)

    def test_impetueux_forces_advantage_on_d20(self):
        n = normalize_d20_roll_input(
            "d20+4", "normal", CombatRollFlags(reckless=True)
        )
        assert n is not None
        self.assertEqual(n.mode, "avantage")

    def test_3d20_rejected(self):
        with self.assertRaises(DiceError):
            normalize_d20_roll_input("3d20", "normal", CombatRollFlags())

    def test_d6_not_hook(self):
        self.assertIsNone(normalize_d20_roll_input("3d6", "normal", CombatRollFlags()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
