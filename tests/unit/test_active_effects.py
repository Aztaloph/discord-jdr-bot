# tests/unit/test_active_effects.py
"""Lot ADR-006 commit A — ActiveEffect, registre et horloge combat."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import RoundStarted
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.active_effect import (
    ActiveEffect,
    ActiveEffectValidationError,
)
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.effects.registry import ActiveEffectRegistry


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _wizard(*, name: str = "Test Mage", dex: int = 14) -> Character:
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
        hp_current=20,
        hp_max=20,
        choices={
            "spellcasting": {
                "cantrips_known": ["fire_bolt"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            }
        },
    )


class SequenceRng:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self) -> int:
        if not self._values:
            raise RuntimeError("SequenceRng épuisé")
        return self._values.pop(0)


class TestActiveEffectValidation(unittest.TestCase):
    def test_rounds_requires_duration(self) -> None:
        with self.assertRaises(ActiveEffectValidationError):
            ActiveEffect(
                effect_id="shield",
                source_id="a",
                target_id="b",
                applied_at_round=1,
                expiry_mode="rounds",
            )

    def test_rounds_requires_positive_duration(self) -> None:
        with self.assertRaises(ActiveEffectValidationError):
            ActiveEffect(
                effect_id="shield",
                source_id="a",
                target_id="b",
                applied_at_round=1,
                expiry_mode="rounds",
                duration_rounds=0,
            )

    def test_concentration_allows_missing_duration(self) -> None:
        effect = ActiveEffect(
            effect_id="blessed",
            source_id="cleric",
            target_id="ally",
            applied_at_round=2,
            expiry_mode="concentration",
        )
        self.assertIsNone(effect.duration_rounds)
        self.assertIsNone(effect.expires_at_round)

    def test_manual_allows_missing_duration(self) -> None:
        effect = ActiveEffect(
            effect_id="custom",
            source_id="a",
            target_id="b",
            applied_at_round=1,
            expiry_mode="manual",
        )
        self.assertIsNone(effect.expires_at_round)


class TestActiveEffectRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ActiveEffectRegistry()

    def _round_effect(
        self,
        *,
        applied_at_round: int,
        duration_rounds: int,
        target_id: str = "target",
        source_id: str = "source",
        effect_id: str = "test_buff",
    ) -> ActiveEffect:
        return ActiveEffect(
            effect_id=effect_id,
            source_id=source_id,
            target_id=target_id,
            applied_at_round=applied_at_round,
            expiry_mode="rounds",
            duration_rounds=duration_rounds,
        )

    def test_add_remove_and_query(self) -> None:
        effect = self._round_effect(applied_at_round=1, duration_rounds=3)
        self.registry.add(effect)
        self.assertEqual(self.registry.all_effects(), (effect,))
        self.assertEqual(
            self.registry.query(target_id="target"),
            (effect,),
        )
        self.assertTrue(self.registry.remove(effect))
        self.assertEqual(self.registry.all_effects(), ())

    def test_add_replaces_same_identity(self) -> None:
        first = self._round_effect(applied_at_round=1, duration_rounds=2)
        second = self._round_effect(applied_at_round=4, duration_rounds=5)
        self.registry.add(first)
        self.registry.add(second)
        self.assertEqual(len(self.registry.all_effects()), 1)
        self.assertEqual(self.registry.all_effects()[0].applied_at_round, 4)

    def test_remove_matching_by_source(self) -> None:
        bless_a = ActiveEffect(
            effect_id="blessed",
            source_id="cleric_a",
            target_id="ally",
            applied_at_round=1,
            expiry_mode="concentration",
        )
        bless_b = ActiveEffect(
            effect_id="blessed",
            source_id="cleric_b",
            target_id="ally",
            applied_at_round=1,
            expiry_mode="concentration",
        )
        self.registry.add(bless_a)
        self.registry.add(bless_b)
        removed = self.registry.remove_matching(source_id="cleric_a")
        self.assertEqual(removed, (bless_a,))
        self.assertEqual(self.registry.query(source_id="cleric_b"), (bless_b,))

    def test_tick_expires_only_round_based_effects(self) -> None:
        rounds_effect = self._round_effect(applied_at_round=1, duration_rounds=1)
        concentration = ActiveEffect(
            effect_id="blessed",
            source_id="cleric",
            target_id="ally",
            applied_at_round=1,
            expiry_mode="concentration",
        )
        self.registry.add(rounds_effect)
        self.registry.add(concentration)

        expired = self.registry.tick(2)

        self.assertEqual(expired, (rounds_effect,))
        self.assertEqual(self.registry.all_effects(), (concentration,))

    def test_adr_round_expiration_example(self) -> None:
        effect = self._round_effect(applied_at_round=3, duration_rounds=10)
        self.assertEqual(effect.expires_at_round, 13)
        self.registry.add(effect)

        for round_number in range(3, 13):
            self.assertEqual(self.registry.tick(round_number), ())
            self.assertEqual(self.registry.all_effects(), (effect,))

        expired = self.registry.tick(13)
        self.assertEqual(expired, (effect,))
        self.assertEqual(self.registry.all_effects(), ())


class TestActiveEffectsCombatIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.bus.subscribe(RoundStarted, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.alice = _wizard(name="Alice", dex=16)
        self.bob = _wizard(name="Bob", dex=10)
        self.char_repo.save(self.alice)
        self.char_repo.save(self.bob)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _create_and_activate(self) -> int:
        state = self.manager.create_combat(
            "guild1",
            "channel1",
            [self.alice.id, self.bob.id],
        )
        activated = self.manager.activate_combat(
            int(state.combat_id),
            rng=SequenceRng([15, 10]),
        )
        return int(activated.combat_id)

    def test_advance_turn_ticks_before_round_started(self) -> None:
        combat_id = self._create_and_activate()
        order = self.manager.load_combat(combat_id).initiative_order
        target_id = order[0]

        self.manager.add_active_effect(
            combat_id,
            ActiveEffect(
                effect_id="short_buff",
                source_id=order[1],
                target_id=target_id,
                applied_at_round=1,
                expiry_mode="rounds",
                duration_rounds=1,
            ),
        )

        counts_at_round_started: dict[int, int] = {}

        def _capture(event: RoundStarted) -> None:
            counts_at_round_started[event.round_number] = len(
                self.manager.query_active_effects(combat_id)
            )

        self.bus.subscribe(RoundStarted, _capture)

        self.manager.advance_turn(combat_id)
        self.manager.advance_turn(combat_id)

        self.assertEqual(counts_at_round_started.get(2), 0)
        self.assertEqual(self.manager.query_active_effects(combat_id), ())

    def test_advance_turn_preserves_concentration_effects_across_rounds(self) -> None:
        combat_id = self._create_and_activate()
        order = self.manager.load_combat(combat_id).initiative_order
        effect = ActiveEffect(
            effect_id="blessed",
            source_id=order[0],
            target_id=order[1],
            applied_at_round=1,
            expiry_mode="concentration",
        )
        self.manager.add_active_effect(combat_id, effect)

        self.manager.advance_turn(combat_id)
        self.manager.advance_turn(combat_id)

        self.assertEqual(self.manager.query_active_effects(combat_id), (effect,))


if __name__ == "__main__":
    unittest.main()
