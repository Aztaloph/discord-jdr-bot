# tests/unit/test_ranger_features.py
"""Tests features Rôdeur Ennemi juré + Explorateur-né (Phase 4.5 — Tâche 3)."""
from __future__ import annotations

import unittest

from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, roll_d20
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine, collect_roll_effects, roll_d20_for_character


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestRangerFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _ranger_effects(self):
        char = Character(
            owner_id="1",
            name="Ranger",
            race_id="human",
            class_id="ranger",
            level=1,
            choices={"favored_enemy_type": "beasts", "favored_terrain": "forest"},
        )
        return collect_roll_effects(char, self.engine)

    def test_favored_enemy_survival_tracking_advantage(self):
        req = D20RollRequest(
            roll_type="ability_check",
            skill="survival",
            ability="wis",
            ability_modifier=1,
            tracking=True,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=self._ranger_effects()),
            rng=SequenceRng([5, 19]),
        )
        self.assertEqual(result.mode, "avantage")
        self.assertEqual(result.kept_value, 19)

    def test_favored_enemy_no_advantage_without_tracking(self):
        req = D20RollRequest(
            roll_type="ability_check",
            skill="survival",
            ability_modifier=1,
            tracking=False,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=self._ranger_effects()),
            rng=SequenceRng([15]),
        )
        self.assertEqual(result.mode, "normal")

    def test_favored_enemy_int_recall_advantage(self):
        req = D20RollRequest(
            roll_type="ability_check",
            ability="int",
            ability_modifier=0,
            recalling_favored_enemy_info=True,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=self._ranger_effects()),
            rng=SequenceRng([4, 13]),
        )
        self.assertEqual(result.mode, "avantage")
        self.assertEqual(result.kept_value, 13)

    def test_favored_enemy_wrong_skill_no_advantage(self):
        req = D20RollRequest(
            roll_type="ability_check",
            skill="athletics",
            tracking=True,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=self._ranger_effects()),
            rng=SequenceRng([10]),
        )
        self.assertEqual(result.mode, "normal")

    def test_natural_explorer_double_proficiency_wis(self):
        req = D20RollRequest(
            roll_type="ability_check",
            ability="wis",
            ability_modifier=2,
            proficiency_bonus=2,
            is_proficient=True,
            skill="survival",
            favored_terrain_related=True,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=self._ranger_effects()),
            rng=SequenceRng([12]),
        )
        self.assertEqual(result.modifier, 6)  # 2 + (2*2)
        self.assertEqual(result.total, 18)
        self.assertTrue(any("maîtrise x2" in e for e in result.applied_effects))

    def test_natural_explorer_no_double_without_proficiency(self):
        req = D20RollRequest(
            roll_type="ability_check",
            ability="int",
            ability_modifier=1,
            proficiency_bonus=2,
            is_proficient=False,
            favored_terrain_related=True,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=self._ranger_effects()),
            rng=SequenceRng([10]),
        )
        self.assertEqual(result.modifier, 1)

    def test_natural_explorer_no_double_unrelated_ability(self):
        req = D20RollRequest(
            roll_type="ability_check",
            ability="str",
            ability_modifier=3,
            proficiency_bonus=2,
            is_proficient=True,
            favored_terrain_related=True,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=self._ranger_effects()),
            rng=SequenceRng([10]),
        )
        self.assertEqual(result.modifier, 5)

    def test_ranger_level_0_no_class_features(self):
        features = self.engine.get_class_features("ranger", level=0)
        self.assertEqual(features, [])

    def test_integration_roll_d20_for_character(self):
        char = Character(
            owner_id="1",
            name="Doudou",
            race_id="halfling",
            class_id="ranger",
            level=1,
        )
        result = roll_d20_for_character(
            D20RollRequest(
                roll_type="ability_check",
                ability="wis",
                skill="survival",
                ability_modifier=1,
                proficiency_bonus=2,
                is_proficient=True,
                favored_terrain_related=True,
            ),
            char,
            self.engine,
            rng=SequenceRng([14]),
        )
        self.assertEqual(result.modifier, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
