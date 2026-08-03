# tests/unit/test_combat_initiative.py
"""Lot C2 — règles d'initiative pures (ordre, départage, avancement de tour)."""
from __future__ import annotations

import unittest

from jdr_engine.rules.combat.initiative import (
    InitiativeRollResult,
    next_active_turn_index,
    sort_initiative_order,
)


class TestInitiativeOrder(unittest.TestCase):
    def test_sort_descending_by_total(self) -> None:
        rolls = [
            InitiativeRollResult("b", 10, 2),
            InitiativeRollResult("a", 15, 0),
            InitiativeRollResult("c", 8, 5),
        ]
        self.assertEqual(sort_initiative_order(rolls), ("a", "c", "b"))

    def test_tie_break_by_combatant_id_ascending(self) -> None:
        rolls = [
            InitiativeRollResult("char_b", 12, 3),
            InitiativeRollResult("char_a", 12, 3),
            InitiativeRollResult("char_c", 10, 5),
        ]
        self.assertEqual(
            sort_initiative_order(rolls),
            ("char_a", "char_b", "char_c"),
        )


class TestTurnAdvancement(unittest.TestCase):
    def test_skip_inactive_combatant(self) -> None:
        order = ("a", "b", "c")
        active = {"a", "c"}

        def is_active(cid: str) -> bool:
            return cid in active

        result = next_active_turn_index(order, 0, is_active=is_active)
        self.assertEqual(result, (2, 0))

    def test_wrap_increments_round(self) -> None:
        order = ("a", "b")
        result = next_active_turn_index(
            order,
            1,
            is_active=lambda _: True,
        )
        self.assertEqual(result, (0, 1))

    def test_no_active_returns_none(self) -> None:
        order = ("a", "b")
        result = next_active_turn_index(
            order,
            0,
            is_active=lambda _: False,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
