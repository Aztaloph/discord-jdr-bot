# tests/unit/test_rogue_features.py
"""Roublard — features SRD 2014 niv. 1-3 (Phase 4.7 Lot A)."""
from __future__ import annotations

import unittest

from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, roll_d20
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.class_features.rogue import (
    roll_sneak_attack_damage,
    sneak_attack_dice_count,
    sneak_attack_eligible,
)
from jdr_engine.rules.roll_effects import collect_roll_effects, enrich_roll_request


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class FixedRoll:
    def __init__(self, total: int, rolls: list[int]):
        self.total = total
        self.rolls = rolls
        self.dice_notation = "mock"
        self.modifier = 0
        self.modifier_label = ""
        self.is_kept = [True] * len(rolls)

    def __call__(self, notation: str):
        return self


class TestSneakAttack(unittest.TestCase):
    def test_dice_progression_level_1_3(self):
        self.assertEqual(sneak_attack_dice_count(1), 1)
        self.assertEqual(sneak_attack_dice_count(2), 1)
        self.assertEqual(sneak_attack_dice_count(3), 2)

    def test_eligible_with_advantage(self):
        self.assertTrue(
            sneak_attack_eligible(
                hit=True,
                finesse_or_ranged=True,
                has_advantage=True,
                ally_within_5ft_of_target=False,
                has_disadvantage=False,
                already_used_this_turn=False,
            )
        )

    def test_eligible_ally_no_disadvantage(self):
        self.assertTrue(
            sneak_attack_eligible(
                hit=True,
                finesse_or_ranged=True,
                has_advantage=False,
                ally_within_5ft_of_target=True,
                has_disadvantage=False,
                already_used_this_turn=False,
            )
        )

    def test_not_eligible_with_disadvantage_without_advantage(self):
        self.assertFalse(
            sneak_attack_eligible(
                hit=True,
                finesse_or_ranged=True,
                has_advantage=False,
                ally_within_5ft_of_target=True,
                has_disadvantage=True,
                already_used_this_turn=False,
            )
        )

    def test_not_eligible_miss(self):
        self.assertFalse(
            sneak_attack_eligible(
                hit=False,
                finesse_or_ranged=True,
                has_advantage=True,
                ally_within_5ft_of_target=False,
                has_disadvantage=False,
                already_used_this_turn=False,
            )
        )

    def test_once_per_turn(self):
        self.assertFalse(
            sneak_attack_eligible(
                hit=True,
                finesse_or_ranged=True,
                has_advantage=True,
                ally_within_5ft_of_target=False,
                has_disadvantage=False,
                already_used_this_turn=True,
            )
        )

    def test_roll_damage_level_3(self):
        mock = FixedRoll(7, [4, 3])
        total, result = roll_sneak_attack_damage(3, rng=mock)
        self.assertEqual(total, 7)
        self.assertEqual(len(result.rolls), 2)


class TestRogueExpertise(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_expertise_doubles_proficiency(self):
        char = Character(
            owner_id="1",
            name="Rogue",
            race_id="human",
            class_id="rogue",
            level=1,
            choices={"expertise_skills": ["stealth", "perception"]},
        )
        effects = collect_roll_effects(char, self.engine)
        req = enrich_roll_request(
            D20RollRequest(
                roll_type="ability_check",
                skill="stealth",
                ability="dex",
                ability_modifier=3,
                proficiency_bonus=2,
                is_proficient=True,
            ),
            char,
        )
        result = roll_d20(D20RollContext(req, effects), rng=SequenceRng([12]))
        self.assertEqual(result.modifier, 7)
        self.assertEqual(result.total, 19)


if __name__ == "__main__":
    unittest.main(verbosity=2)
