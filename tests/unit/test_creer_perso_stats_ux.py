# tests/unit/test_creer_perso_stats_ux.py
"""UX étape 2 /creer-perso — modes point buy et 4d6."""
from __future__ import annotations

import unittest

from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS
from jdr_engine.rules.character_creation.point_buy import (
    POINT_BUY_BUDGET,
    points_remaining,
    validate_point_buy_scores,
)
from jdr_engine.rules.character_creation.random_assign import RandomAssignState


def enter_point_buy_mode(base_scores: dict[str, int] | None = None) -> dict[str, int]:
    """Simule le basculement vers le point buy (scores remis à 8)."""
    scores = dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
    if base_scores:
        scores.update(base_scores)
    return scores


def enter_random_mode(pool: list[int] | None = None) -> RandomAssignState:
    """Simule le basculement vers le mode 4d6."""
    if pool is None:
        return RandomAssignState.roll_new()
    return RandomAssignState.from_pool(pool)


class TestPointBuyMode(unittest.TestCase):
    def test_default_budget_27(self):
        scores = enter_point_buy_mode()
        validate_point_buy_scores(scores)
        self.assertEqual(points_remaining(scores), POINT_BUY_BUDGET)

    def test_valid_spread_costs_official(self):
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


class TestRandomAssignUx(unittest.TestCase):
    def test_all_six_rolls_assigned_no_duplicate(self):
        state = enter_random_mode([13, 11, 11, 10, 10, 9])
        for aid, idx in zip(DEFAULT_ABILITY_IDS, range(6)):
            state.assign(aid, idx)
        self.assertTrue(state.is_complete())
        scores = state.to_base_scores()
        self.assertEqual(len(scores), 6)
        self.assertEqual(set(scores.values()), {13, 11, 10, 9})
        self.assertEqual(scores["str"], 13)

    def test_sorted_pool_display(self):
        state = RandomAssignState.from_pool([9, 13, 11, 10, 11, 10])
        self.assertEqual(state.sorted_pool_values(), [13, 11, 11, 10, 10, 9])

    def test_reject_double_roll_assignment(self):
        state = enter_random_mode([15, 14, 13, 12, 11, 10])
        state.assign("str", 0)
        with self.assertRaises(ValueError):
            state.assign("dex", 0)


class TestModeSwitching(unittest.TestCase):
    def test_switch_point_buy_to_random_clears_scores(self):
        scores = enter_point_buy_mode({"str": 15, "dex": 14})
        random_state = enter_random_mode([12, 12, 11, 11, 10, 9])
        self.assertIsNotNone(random_state)
        self.assertEqual(len(random_state.unassigned_abilities()), 6)
        # Retour point buy : scores repartent de 8
        scores = enter_point_buy_mode()
        self.assertTrue(all(scores[aid] == 8 for aid in DEFAULT_ABILITY_IDS))

    def test_switch_random_to_point_buy_discards_partial_assign(self):
        state = enter_random_mode([15, 14, 13, 12, 11, 10])
        state.assign("str", 0)
        state.assign("dex", 1)
        scores = enter_point_buy_mode()
        validate_point_buy_scores(scores)
        self.assertEqual(points_remaining(scores), POINT_BUY_BUDGET)


if __name__ == "__main__":
    unittest.main(verbosity=2)
