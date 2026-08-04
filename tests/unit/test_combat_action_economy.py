# tests/unit/test_combat_action_economy.py
"""Lot C4 — économie d'actions par tour."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import ActionConsumed, TurnStarted
from jdr_engine.dice.d20 import D20RollRequest
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.action_budget import ActionBudgetExhaustedError
from jdr_engine.game.combat_manager import (
    CombatManager,
    NotCombatantTurnError,
)
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine


class RandSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self, a: int, b: int) -> int:
        return self._values.pop(0)


class InitiativeSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self) -> int:
        return self._values.pop(0)


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _wizard(*, name: str, dex: int = 16, hp: int = 20) -> Character:
    return Character(
        owner_id="111",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="wizard",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 8,
                "dex": dex,
                "con": 12,
                "int": 16,
                "wis": 10,
                "cha": 10,
            }
        ),
        hp_current=hp,
        hp_max=hp,
        choices={
            "spellcasting": {
                "cantrips_known": ["fire_bolt"],
                "spells_prepared": ["burning_hands"],
                "slots_used": {},
            }
        },
    )


def _ranger(*, name: str = "Rodeur") -> Character:
    return Character(
        owner_id="112",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="ranger",
        level=2,
        ability_scores=AbilityScores(
            scores={
                "str": 12,
                "dex": 14,
                "con": 12,
                "int": 10,
                "wis": 14,
                "cha": 10,
            }
        ),
        hp_current=24,
        hp_max=24,
        choices={
            "spellcasting": {
                "spells_known": ["hunters_mark"],
                "slots_used": {},
            }
        },
    )


def _attack_request() -> D20RollRequest:
    return D20RollRequest(
        roll_type="attack",
        ability_modifier=5,
        proficiency_bonus=2,
        is_proficient=True,
        ability="dex",
    )


class TestActionEconomy(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.bus.subscribe(ActionConsumed, self.events.append)
        self.bus.subscribe(TurnStarted, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.alice = _wizard(name="Alice", dex=16)
        self.bob = _wizard(name="Bob", dex=10, hp=30)
        self.ranger = _ranger()
        for char in (self.alice, self.bob, self.ranger):
            self.char_repo.save(char)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _activate(self, *character_ids: str) -> tuple[int, dict[str, str], str]:
        state = self.manager.create_combat("guild1", "channel1", list(character_ids))
        state = self.manager.activate_combat(
            int(state.combat_id), rng=InitiativeSequence([14, 8, 10])
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        active_id = state.initiative_order[state.turn_index]
        return int(state.combat_id), id_map, active_id

    def test_budget_initialized_on_turn_started(self) -> None:
        combat_id, id_map, active_id = self._activate(self.alice.id, self.bob.id)
        combatant = self.manager.load_combat(combat_id).combatants[active_id]
        self.assertIsNotNone(combatant.action_budget)
        assert combatant.action_budget is not None
        self.assertTrue(combatant.action_budget.has_action)
        self.assertTrue(combatant.action_budget.has_reaction)

    def test_second_attack_same_turn_refused(self) -> None:
        combat_id, id_map, active_id = self._activate(self.alice.id, self.bob.id)
        other_id = id_map[self.bob.id] if active_id == id_map[self.alice.id] else id_map[self.alice.id]
        attacker_id = active_id
        target_id = other_id

        self.manager.resolve_attack_roll(
            combat_id, attacker_id, target_id, _attack_request(), rng=RandSequence([15])
        )
        with self.assertRaises(ActionBudgetExhaustedError):
            self.manager.resolve_attack_roll(
                combat_id,
                attacker_id,
                target_id,
                _attack_request(),
                rng=RandSequence([16]),
            )
        self.assertEqual(len([e for e in self.events if isinstance(e, ActionConsumed)]), 1)

    def test_attack_off_turn_refused(self) -> None:
        combat_id, id_map, active_id = self._activate(self.alice.id, self.bob.id)
        inactive_id = id_map[self.bob.id] if active_id == id_map[self.alice.id] else id_map[self.alice.id]
        with self.assertRaises(NotCombatantTurnError):
            self.manager.resolve_attack_roll(
                combat_id,
                inactive_id,
                active_id,
                _attack_request(),
                rng=RandSequence([15]),
            )

    def test_reaction_consumable_off_turn(self) -> None:
        combat_id, id_map, active_id = self._activate(self.alice.id, self.bob.id)
        other_id = id_map[self.bob.id] if active_id == id_map[self.alice.id] else id_map[self.alice.id]
        state = self.manager.consume_reaction(combat_id, other_id)
        budget = state.combatants[other_id].action_budget
        assert budget is not None
        self.assertFalse(budget.has_reaction)

    def test_reaction_persists_until_own_turn_started(self) -> None:
        combat_id, id_map, active_id = self._activate(self.alice.id, self.bob.id)
        other_id = id_map[self.bob.id] if active_id == id_map[self.alice.id] else id_map[self.alice.id]
        self.manager.consume_reaction(combat_id, other_id)
        budget = self.manager.load_combat(combat_id).combatants[other_id].action_budget
        assert budget is not None
        self.assertFalse(budget.has_reaction)
        self.manager.advance_turn(combat_id)
        refreshed = self.manager.load_combat(combat_id).combatants[other_id].action_budget
        assert refreshed is not None
        self.assertTrue(refreshed.has_reaction)

    def test_reaction_reset_on_own_turn_started(self) -> None:
        combat_id, id_map, active_id = self._activate(self.alice.id, self.bob.id)
        alice_id = id_map[self.alice.id]
        bob_id = id_map[self.bob.id]
        if active_id == alice_id:
            self.manager.advance_turn(combat_id)
        self.manager.consume_reaction(combat_id, alice_id)
        self.manager.advance_turn(combat_id)
        budget = self.manager.load_combat(combat_id).combatants[alice_id].action_budget
        assert budget is not None
        self.assertTrue(budget.has_reaction)

    def test_hunters_mark_uses_bonus_action(self) -> None:
        combat_id, id_map, active_id = self._activate(self.ranger.id, self.bob.id)
        if active_id != id_map[self.ranger.id]:
            self.skipTest("Le rôdeur doit jouer en premier pour ce test.")
        caster_id = id_map[self.ranger.id]
        target_id = id_map[self.bob.id]
        self.manager.cast_hunters_mark(combat_id, caster_id, target_id)
        budget = self.manager.load_combat(combat_id).combatants[caster_id].action_budget
        assert budget is not None
        self.assertFalse(budget.has_bonus_action)
        self.assertTrue(budget.has_action)
        with self.assertRaises(ActionBudgetExhaustedError):
            self.manager.cast_hunters_mark(combat_id, caster_id, target_id)

    def test_budget_survives_save_reload(self) -> None:
        combat_id, id_map, active_id = self._activate(self.alice.id, self.bob.id)
        other_id = id_map[self.bob.id] if active_id == id_map[self.alice.id] else id_map[self.alice.id]
        self.manager.resolve_attack_roll(
            combat_id, active_id, other_id, _attack_request(), rng=RandSequence([12])
        )
        snapshot = self.manager.load_combat(combat_id).combatants[active_id].action_budget
        reloaded = self.manager.load_combat(combat_id)
        self.assertEqual(reloaded.combatants[active_id].action_budget, snapshot)


if __name__ == "__main__":
    unittest.main()
