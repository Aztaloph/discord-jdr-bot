# tests/unit/test_d20_hook.py
"""Tests du hook central d20 (Phase 4.5 — Tâche 1)."""
from __future__ import annotations

import unittest

from jdr_engine.dice.d20 import (
    D20RollContext,
    D20RollRequest,
    roll_d20,
)


class SequenceRng:
    """RNG déterministe pour les tests."""

    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        if self._index >= len(self._values):
            raise RuntimeError("SequenceRng épuisé")
        value = self._values[self._index]
        self._index += 1
        if not low <= value <= high:
            raise ValueError(f"Valeur {value} hors plage [{low}, {high}]")
        return value


class TestD20HookBasics(unittest.TestCase):
    """Cas nominaux et limites du hook sans effet."""

    def test_normal_roll_total(self):
        req = D20RollRequest(
            roll_type="ability_check",
            ability_modifier=3,
            ability="dex",
        )
        result = roll_d20(D20RollContext(request=req), rng=SequenceRng([14]))
        self.assertEqual(result.kept_value, 14)
        self.assertEqual(result.total, 17)
        self.assertEqual(result.mode, "normal")
        self.assertFalse(result.rerolled)

    def test_advantage_keeps_best(self):
        req = D20RollRequest(
            roll_type="attack",
            ability_modifier=5,
            base_mode="avantage",
        )
        result = roll_d20(D20RollContext(request=req), rng=SequenceRng([4, 18]))
        self.assertEqual(result.kept_value, 18)
        self.assertEqual(result.total, 23)
        self.assertEqual(result.mode, "avantage")

    def test_external_advantage_via_base_mode(self):
        req = D20RollRequest(
            roll_type="attack",
            base_mode="avantage",
            ability_modifier=0,
        )
        result = roll_d20(D20RollContext(request=req), rng=SequenceRng([7, 16]))
        self.assertEqual(result.mode, "avantage")
        self.assertEqual(result.kept_value, 16)

    def test_disadvantage_keeps_worst(self):
        req = D20RollRequest(
            roll_type="saving_throw",
            base_mode="desavantage",
            ability_modifier=2,
        )
        result = roll_d20(D20RollContext(request=req), rng=SequenceRng([19, 6]))
        self.assertEqual(result.mode, "desavantage")
        self.assertEqual(result.kept_value, 6)
        self.assertEqual(result.total, 8)

    def test_advantage_and_disadvantage_cancel(self):
        effects = [
            {
                "type": "advantage",
                "context": "saving_throw",
                "versus": "frightened",
            }
        ]
        ctx = D20RollContext(
            request=D20RollRequest(
                roll_type="saving_throw",
                save_versus_condition="frightened",
                base_mode="desavantage",
            ),
            effects=effects,
        )
        result = roll_d20(ctx, rng=SequenceRng([12]))
        self.assertEqual(result.mode, "normal")

    def test_proficiency_in_modifier(self):
        req = D20RollRequest(
            roll_type="ability_check",
            ability_modifier=2,
            proficiency_bonus=3,
            is_proficient=True,
            skill="survival",
        )
        result = roll_d20(D20RollContext(request=req), rng=SequenceRng([10]))
        self.assertEqual(result.modifier, 5)
        self.assertEqual(result.total, 15)

    def test_natural_20_and_natural_1_flags(self):
        r20 = roll_d20(
            D20RollContext(request=D20RollRequest(roll_type="attack")),
            rng=SequenceRng([20]),
        )
        r1 = roll_d20(
            D20RollContext(request=D20RollRequest(roll_type="attack")),
            rng=SequenceRng([1]),
        )
        self.assertTrue(r20.natural_20)
        self.assertFalse(r20.natural_1)
        self.assertTrue(r1.natural_1)
        self.assertFalse(r1.natural_20)


class TestD20HookEffectPipeline(unittest.TestCase):
    """Vérifie que les effets passent bien par le hook avant/après."""

    def test_lucky_reroll_after_kept_die(self):
        req = D20RollRequest(roll_type="attack", ability_modifier=0)
        effects = [
            {
                "type": "reroll_natural_1",
                "contexts": ["attack", "ability_check", "saving_throw"],
                "source_id": "lucky",
            }
        ]
        result = roll_d20(
            D20RollContext(request=req, effects=effects),
            rng=SequenceRng([1, 8]),
        )
        self.assertTrue(result.rerolled)
        self.assertEqual(result.kept_value, 8)
        self.assertEqual(result.rolls, [1, 8])
        self.assertIn("relance nat. 1", result.applied_effects[0])

    def test_lucky_not_triggered_on_nat_2(self):
        req = D20RollRequest(roll_type="ability_check")
        effects = [{"type": "reroll_natural_1", "contexts": ["ability_check"]}]
        result = roll_d20(
            D20RollContext(request=req, effects=effects),
            rng=SequenceRng([2]),
        )
        self.assertFalse(result.rerolled)
        self.assertEqual(result.kept_value, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
