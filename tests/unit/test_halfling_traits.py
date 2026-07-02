# tests/unit/test_halfling_traits.py
"""Tests traits Halfelin Brave + Chanceux (Phase 4.5 — Tâche 2)."""
from __future__ import annotations

import unittest

from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, roll_d20
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine, roll_d20_for_character


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestHalflingBrave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_brave_advantage_on_frightened_save(self):
        effects = self.engine.get_race_traits("halfling")
        effect_dicts = []
        for t in effects:
            if t.entry_id == "brave":
                effect_dicts.extend(t.definition.mechanics.get("effects", []))
        self.assertTrue(effect_dicts)

        req = D20RollRequest(
            roll_type="saving_throw",
            save_versus_condition="frightened",
            ability_modifier=1,
            ability="wis",
        )
        result = roll_d20(
            D20RollContext(request=req, effects=effect_dicts),
            rng=SequenceRng([3, 17]),
        )
        self.assertEqual(result.mode, "avantage")
        self.assertEqual(result.kept_value, 17)
        self.assertTrue(any("avantage" in e for e in result.applied_effects))

    def test_brave_no_advantage_other_condition(self):
        effects = []
        for t in self.engine.get_race_traits("halfling"):
            if t.entry_id == "brave":
                effects.extend(t.definition.mechanics.get("effects", []))

        req = D20RollRequest(
            roll_type="saving_throw",
            save_versus_condition="poisoned",
            ability_modifier=0,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=effects),
            rng=SequenceRng([12]),
        )
        self.assertEqual(result.mode, "normal")

    def test_brave_via_character_integration(self):
        char = Character(
            owner_id="1",
            name="Doudou",
            race_id="halfling",
            class_id="ranger",
            level=1,
        )
        result = roll_d20_for_character(
            D20RollRequest(
                roll_type="saving_throw",
                save_versus_condition="frightened",
                ability_modifier=0,
            ),
            char,
            self.engine,
            rng=SequenceRng([2, 14]),
        )
        self.assertEqual(result.mode, "avantage")


class TestHalflingLucky(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_lucky_reroll_on_natural_1_attack(self):
        char = Character(
            owner_id="1",
            name="Test",
            race_id="halfling",
            class_id="fighter",
            level=1,
        )
        result = roll_d20_for_character(
            D20RollRequest(roll_type="attack", ability_modifier=4),
            char,
            self.engine,
            rng=SequenceRng([1, 11]),
        )
        self.assertTrue(result.rerolled)
        self.assertEqual(result.kept_value, 11)
        self.assertEqual(result.total, 15)

    def test_lucky_reroll_can_still_be_1(self):
        char = Character(
            owner_id="1",
            name="Test",
            race_id="halfling",
            class_id="fighter",
            level=1,
        )
        result = roll_d20_for_character(
            D20RollRequest(roll_type="saving_throw", ability_modifier=0),
            char,
            self.engine,
            rng=SequenceRng([1, 1]),
        )
        self.assertTrue(result.rerolled)
        self.assertEqual(result.kept_value, 1)
        self.assertTrue(result.natural_1)

    def test_lucky_not_on_d6_legacy_roll_unaffected(self):
        """Le hook d20 est séparé de roll('d6') — pas de relance sur d6."""
        from jdr_engine.dice import roll

        result = roll("d6")
        self.assertEqual(len(result.rolls), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
