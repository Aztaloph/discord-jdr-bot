# tests/unit/test_bless_multisource.py
"""Lot ADR-006 commit B — bless multi-source (deux clercs)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import EventBus
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine


class InitiativeSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self) -> int:
        if not self._values:
            raise RuntimeError("InitiativeSequence épuisé")
        return self._values.pop(0)


class RandSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self, a: int, b: int) -> int:
        if not self._values:
            raise RuntimeError("RandSequence épuisé")
        return self._values.pop(0)


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _cleric(*, owner_id: str, name: str, con: int = 12) -> Character:
    return Character(
        owner_id=owner_id,
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="cleric",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 10,
                "dex": 10,
                "con": con,
                "int": 10,
                "wis": 16,
                "cha": 10,
            }
        ),
        hp_current=22,
        hp_max=22,
        choices={
            "spellcasting": {
                "cantrips_known": ["sacred_flame"],
                "spells_prepared": ["bless", "cure_wounds"],
                "slots_used": {},
            }
        },
    )


def _fighter(*, name: str = "Guerrier") -> Character:
    return Character(
        owner_id="200",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="fighter",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 16,
                "dex": 12,
                "con": 14,
                "int": 10,
                "wis": 10,
                "cha": 10,
            }
        ),
        hp_current=30,
        hp_max=30,
    )


class TestBlessMultisource(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        init_database(self.db_path)
        self.engine = _engine()
        self.bus = EventBus()
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.cleric_a = _cleric(owner_id="101", name="Clerc A")
        self.cleric_b = _cleric(owner_id="102", name="Clerc B", con=10)
        self.fighter = _fighter()
        for char in (self.cleric_a, self.cleric_b, self.fighter):
            self.char_repo.save(char)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _setup_fight(self) -> tuple[str, str, str, int]:
        state = self.manager.create_combat(
            "guild1",
            "channel1",
            [self.cleric_a.id, self.cleric_b.id, self.fighter.id],
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([18, 14, 10]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        return (
            id_map[self.cleric_a.id],
            id_map[self.cleric_b.id],
            id_map[self.fighter.id],
            int(state.combat_id),
        )

    def test_two_bless_on_same_target_coexist(self) -> None:
        cleric_a_id, cleric_b_id, fighter_id, combat_id = self._setup_fight()
        self.manager.cast_bless(combat_id, cleric_a_id, [fighter_id])
        self.manager.advance_turn(combat_id)
        self.manager.cast_bless(combat_id, cleric_b_id, [fighter_id])

        effects = self.manager.query_active_effects(
            combat_id,
            effect_id="blessed",
            target_id=fighter_id,
        )
        sources = {effect.source_id for effect in effects}
        self.assertEqual(sources, {cleric_a_id, cleric_b_id})

    def test_concentration_break_removes_only_matching_source(self) -> None:
        cleric_a_id, cleric_b_id, fighter_id, combat_id = self._setup_fight()
        self.manager.cast_bless(combat_id, cleric_a_id, [fighter_id])
        self.manager.advance_turn(combat_id)
        self.manager.cast_bless(combat_id, cleric_b_id, [fighter_id])

        self.manager.apply_damage(
            combat_id,
            cleric_a_id,
            damage_amount=24,
            source_id=fighter_id,
            rng=RandSequence([1]),
        )

        self.assertFalse(
            self.manager.query_active_effects(
                combat_id,
                effect_id="blessed",
                target_id=fighter_id,
                source_id=cleric_a_id,
            )
        )
        self.assertTrue(
            self.manager.query_active_effects(
                combat_id,
                effect_id="blessed",
                target_id=fighter_id,
                source_id=cleric_b_id,
            )
        )

    def test_bless_effects_persist_in_blob_after_cast(self) -> None:
        cleric_a_id, cleric_b_id, fighter_id, combat_id = self._setup_fight()
        self.manager.cast_bless(combat_id, cleric_a_id, [fighter_id])
        self.manager.advance_turn(combat_id)
        self.manager.cast_bless(combat_id, cleric_b_id, [fighter_id])

        loaded = self.manager.load_combat(combat_id)
        sources = {
            effect.source_id
            for effect in loaded.active_effects
            if effect.effect_id == "blessed" and effect.target_id == fighter_id
        }
        self.assertEqual(sources, {cleric_a_id, cleric_b_id})


if __name__ == "__main__":
    unittest.main()
