# tests/unit/test_fighter_features.py
"""Guerrier — features SRD 2014 niv. 1-3 (Phase 4.7 Lot A)."""
from __future__ import annotations

import unittest

from jdr_engine.application.character_service import CharacterService
from jdr_engine.application.dto.character_commands import CreateCharacterCommand
from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, roll_d20
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.character_repository import JsonCharacterRepository
from jdr_engine.rules import RuleEngine, roll_d20_for_character
from jdr_engine.rules.class_features.fighter import (
    action_surge_available,
    roll_second_wind_healing,
    second_wind_available,
    use_action_surge,
    use_second_wind,
)
from jdr_engine.rules.roll_effects import collect_roll_effects

import tempfile
from pathlib import Path


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


class TestFighterResources(unittest.TestCase):
    def test_second_wind_healing(self):
        mock = FixedRoll(12, [7])
        total, result = roll_second_wind_healing(3, rng=mock)
        self.assertEqual(total, 12)
        self.assertEqual(result.rolls, [7])

    def test_second_wind_once_between_rests(self):
        choices = {}
        self.assertTrue(second_wind_available(choices))
        choices = use_second_wind(choices)
        self.assertFalse(second_wind_available(choices))

    def test_action_surge_once_between_rests(self):
        choices = {}
        self.assertTrue(action_surge_available(choices))
        choices = use_action_surge(choices)
        self.assertFalse(action_surge_available(choices))


class TestFighterArchery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_archery_plus_two_ranged_attack(self):
        char = Character(
            owner_id="1",
            name="Guer",
            race_id="human",
            class_id="fighter",
            level=1,
            choices={"fighting_style": "archery"},
        )
        effects = collect_roll_effects(char, self.engine)
        req = D20RollRequest(
            roll_type="attack",
            ability_modifier=3,
            ranged_weapon=True,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=effects),
            rng=SequenceRng([14]),
        )
        self.assertEqual(result.modifier, 5)
        self.assertEqual(result.total, 19)

    def test_archery_no_bonus_melee(self):
        char = Character(
            owner_id="1",
            name="Guer",
            race_id="human",
            class_id="fighter",
            level=1,
            choices={"fighting_style": "archery"},
        )
        effects = collect_roll_effects(char, self.engine)
        req = D20RollRequest(
            roll_type="attack",
            ability_modifier=3,
            melee_weapon=True,
        )
        result = roll_d20(
            D20RollContext(request=req, effects=effects),
            rng=SequenceRng([14]),
        )
        self.assertEqual(result.modifier, 3)


class TestFighterClassFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_level_2_has_action_surge_not_level_1(self):
        f1 = self.engine.get_class_features("fighter", 1)
        f2 = self.engine.get_class_features("fighter", 2)
        self.assertEqual({t.entry_id for t in f1}, {"fighting_style", "second_wind"})
        self.assertIn("action_surge", {t.entry_id for t in f2})

    def test_level_3_martial_archetype_has_champion_option(self):
        features = self.engine.get_class_features("fighter", 3)
        archetype = next(t for t in features if t.entry_id == "martial_archetype")
        choice = archetype.definition.mechanics.get("choice") or {}
        options = choice.get("options") or []
        ids = {o["id"] if isinstance(o, dict) else o for o in options}
        self.assertEqual(ids, {"champion"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
