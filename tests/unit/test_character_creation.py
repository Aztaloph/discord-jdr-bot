# tests/unit/test_character_creation.py
"""Création de personnage — point buy, 4d6, finalisation, anti-doublon."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import (
    CharacterService,
    CharacterValidationError,
)
from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_creation.starting_spells import build_starting_spellcasting
from jdr_engine.rules.character_creation.point_buy import (
    POINT_BUY_BUDGET,
    POINT_BUY_MAX,
    POINT_BUY_MIN,
    points_remaining,
    validate_point_buy_scores,
)
from jdr_engine.rules.character_creation.random_assign import RandomAssignState
from jdr_engine.rules.character_creation.rolling import roll_4d6_drop_lowest, roll_ability_score_pool


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestPointBuy(unittest.TestCase):
    def test_budget_27_all_eights(self):
        scores = dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
        validate_point_buy_scores(scores)
        self.assertEqual(points_remaining(scores), POINT_BUY_BUDGET)

    def test_bounds_8_15(self):
        scores = {
            "str": 15,
            "dex": 14,
            "con": 13,
            "int": 12,
            "wis": 10,
            "cha": 8,
        }
        validate_point_buy_scores(scores)
        self.assertEqual(points_remaining(scores), 0)

    def test_reject_over_budget(self):
        scores = dict.fromkeys(DEFAULT_ABILITY_IDS, 15)
        with self.assertRaises(ValueError):
            validate_point_buy_scores(scores)

    def test_reject_below_min(self):
        scores = dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
        scores["str"] = 7
        with self.assertRaises(ValueError):
            validate_point_buy_scores(scores)

    def test_reject_above_max(self):
        scores = dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
        scores["str"] = 16
        with self.assertRaises(ValueError):
            validate_point_buy_scores(scores)


class TestRolling(unittest.TestCase):
    def test_4d6_drop_lowest(self):
        total, rolls = roll_4d6_drop_lowest(rng=SequenceRng([1, 2, 3, 6]))
        self.assertEqual(rolls, [1, 2, 3, 6])
        self.assertEqual(total, 11)  # 2+3+6

    def test_pool_six_scores(self):
        rng = SequenceRng([1, 2, 3, 6] * 6)
        pool = roll_ability_score_pool(rng=rng)
        self.assertEqual(len(pool), 6)
        self.assertTrue(all(3 <= s <= 18 for s in pool))


class TestRandomAssignMode(unittest.TestCase):
    """Simule le passage en mode aléatoire (4d6) sans Discord."""

    def test_roll_and_assign_all_six(self):
        state = RandomAssignState.from_pool([15, 14, 14, 13, 12, 10])
        self.assertEqual(len(state.unassigned_roll_indices()), 6)
        order = [("str", 0), ("dex", 1), ("con", 2), ("int", 3), ("wis", 4), ("cha", 5)]
        for ability_id, roll_index in order:
            state.pending_ability = ability_id
            state.pending_roll_index = roll_index
            state.assign(ability_id, roll_index)
        self.assertTrue(state.is_complete())
        scores = state.to_base_scores()
        self.assertEqual(scores["str"], 15)
        self.assertEqual(scores["dex"], 14)
        self.assertEqual(scores["int"], 13)

    def test_duplicate_roll_values_use_unique_indices(self):
        state = RandomAssignState.from_pool([14, 14, 12, 11, 10, 9])
        indices = state.unassigned_roll_indices()
        self.assertEqual(len(indices), 6)
        self.assertEqual(len(set(indices)), 6)
        state.assign("str", 0)
        state.assign("dex", 1)
        self.assertEqual(state.entries[0].value, state.entries[1].value)
        self.assertNotEqual(state.entries[0].ability_id, state.entries[1].ability_id)

    def test_reject_double_assignment(self):
        state = RandomAssignState.from_pool([15, 14, 13, 12, 11, 10])
        state.assign("str", 0)
        with self.assertRaises(ValueError):
            state.assign("dex", 0)


class TestFinalizeCharacter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_wizard_hp_and_spellcasting(self):
        scores = dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
        scores["int"] = 15
        scores["con"] = 14
        char = finalize_new_character(
            name="Test Mage",
            race_id="human",
            class_id="wizard",
            owner_id="1",
            guild_id="100",
            base_scores=scores,
            engine=self.engine,
            skills=["arcana", "history"],
        )
        self.assertEqual(char.hp_current, char.hp_max)
        self.assertIn("fire_bolt", char.choices["spellcasting"]["cantrips_known"])
        self.assertNotIn("scorching_ray", char.choices["spellcasting"]["spells_prepared"])

    def test_cleric_wis_spellcasting(self):
        sc = build_starting_spellcasting("cleric")
        self.assertIn("sacred_flame", sc["cantrips_known"])
        self.assertIn("cure_wounds", sc["spells_prepared"])
        self.assertNotIn("spiritual_weapon", sc["spells_prepared"])


class TestMultipleCreation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_allow_multiple_characters_same_guild(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            init_database(db)
            repo = SqliteCharacterRepository(db)
            service = CharacterService(repo, self.engine)
            scores = dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
            scores["int"] = 14
            scores["con"] = 12
            first = service.create_from_wizard(
                owner_id="42",
                guild_id="999",
                name="Premier",
                race_id="human",
                class_id="wizard",
                base_scores=scores,
                skills=["arcana", "history"],
            )
            scores_cleric = dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
            scores_cleric["wis"] = 15
            second = service.create_from_wizard(
                owner_id="42",
                guild_id="999",
                name="Second",
                race_id="human",
                class_id="cleric",
                base_scores=scores_cleric,
                skills=["medicine", "religion"],
                specialization="life",
            )
            self.assertNotEqual(first.id, second.id)
            active = service.get_active_character("42", "999")
            self.assertIsNotNone(active)
            self.assertEqual(active.id, first.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
