# tests/unit/test_barbarian_features.py
"""Barbare — features SRD 2014 niv. 1-3 (Phase 4.7 Lot A)."""
from __future__ import annotations

import unittest

from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, roll_d20
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.class_features.barbarian import (
    activate_reckless_attack,
    end_rage,
    rage_damage_bonus,
    rage_resistances,
    start_rage,
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


class TestBarbarianResources(unittest.TestCase):
    def test_rage_damage_bonus_level_1_3(self):
        self.assertEqual(rage_damage_bonus(1), 2)
        self.assertEqual(rage_damage_bonus(3), 2)

    def test_rage_resistances(self):
        self.assertEqual(
            rage_resistances(),
            frozenset({"bludgeoning", "piercing", "slashing"}),
        )

    def test_rage_state_toggle(self):
        choices = start_rage({}, level=1)
        self.assertTrue(choices["feature_state"]["rage_active"])
        choices = end_rage(choices)
        self.assertFalse(choices["feature_state"]["rage_active"])


class TestBarbarianD20Hook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _barbarian(self, level: int = 2, **state) -> Character:
        choices = {"feature_state": state}
        return Character(
            owner_id="1",
            name="Barb",
            race_id="human",
            class_id="barbarian",
            level=level,
            choices=choices,
        )

    def test_rage_advantage_str_save(self):
        char = self._barbarian(rage_active=True)
        effects = collect_roll_effects(char, self.engine)
        req = enrich_roll_request(
            D20RollRequest(
                roll_type="saving_throw",
                ability="str",
                ability_modifier=2,
            ),
            char,
        )
        result = roll_d20(D20RollContext(req, effects), rng=SequenceRng([4, 17]))
        self.assertEqual(result.mode, "avantage")

    def test_reckless_advantage_str_melee_attack(self):
        char = self._barbarian(reckless_active=True)
        effects = collect_roll_effects(char, self.engine)
        req = enrich_roll_request(
            D20RollRequest(
                roll_type="attack",
                str_melee_attack=True,
            ),
            char,
        )
        result = roll_d20(D20RollContext(req, effects), rng=SequenceRng([5, 16]))
        self.assertEqual(result.mode, "avantage")

    def test_attack_vs_reckless_target_advantage(self):
        char = self._barbarian(level=2)
        effects = collect_roll_effects(char, self.engine)
        req = D20RollRequest(roll_type="attack", target_reckless=True)
        result = roll_d20(D20RollContext(req, effects), rng=SequenceRng([3, 18]))
        self.assertEqual(result.mode, "avantage")

    def test_danger_sense_dex_save_visible(self):
        char = self._barbarian(level=2)
        effects = collect_roll_effects(char, self.engine)
        req = D20RollRequest(
            roll_type="saving_throw",
            ability="dex",
            visible_effect=True,
        )
        result = roll_d20(D20RollContext(req, effects), rng=SequenceRng([6, 19]))
        self.assertEqual(result.mode, "avantage")

    def test_danger_sense_not_level_1(self):
        char = self._barbarian(level=1)
        effects = collect_roll_effects(char, self.engine)
        self.assertFalse(any(t.entry_id == "danger_sense" for t in self.engine.get_class_features("barbarian", 1) if False))
        features = {t.entry_id for t in self.engine.get_class_features("barbarian", 1)}
        self.assertNotIn("danger_sense", features)


if __name__ == "__main__":
    unittest.main(verbosity=2)
