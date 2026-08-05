# tests/unit/test_combat_buffs.py
"""Lot B4 — buffs overlay combat (hunters_mark, bless)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import ConcentrationBroken, DamageDealt
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.state import get_spellcasting_state


class RandSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self, a: int, b: int) -> int:
        if not self._values:
            raise RuntimeError("RandSequence épuisé")
        return self._values.pop(0)


class InitiativeSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self) -> int:
        if not self._values:
            raise RuntimeError("InitiativeSequence épuisé")
        return self._values.pop(0)


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _ranger(*, name: str = "Rodeur", con: int = 12) -> Character:
    return Character(
        owner_id="111",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="ranger",
        level=2,
        ability_scores=AbilityScores(
            scores={
                "str": 12,
                "dex": 16,
                "con": con,
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


def _wizard(*, name: str = "Mage", hp: int = 20) -> Character:
    return Character(
        owner_id="112",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="wizard",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 8,
                "dex": 14,
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
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            }
        },
    )


class TestHuntersMarkBuff(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        init_database(self.db_path)
        self.engine = _engine()
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.bus.subscribe(DamageDealt, self.events.append)
        self.bus.subscribe(ConcentrationBroken, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.ranger = _ranger(name="Alice")
        self.wizard = _wizard(name="Bob")
        self.char_repo.save(self.ranger)
        self.char_repo.save(self.wizard)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _active_fight(self) -> tuple[str, str, int]:
        state = self.manager.create_combat(
            "guild1", "channel1", [self.ranger.id, self.wizard.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([10, 8]),
        )
        ranger_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.ranger.id
        )
        wizard_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.wizard.id
        )
        return ranger_id, wizard_id, int(state.combat_id)

    def test_hunters_mark_adds_1d6_damage_when_caster_hits_marked_target(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)
        wizard_hp = self.manager.load_combat(combat_id).combatants[wizard_id].hp_current

        state, resolution = self.manager.apply_damage(
            combat_id,
            wizard_id,
            damage_amount=5,
            source_id=ranger_id,
            rng=RandSequence([4]),
        )
        self.assertEqual(resolution.application.damage_dealt, 9)
        self.assertEqual(state.combatants[wizard_id].hp_current, wizard_hp - 9)

    def test_hunters_mark_no_bonus_unmarked_target(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)

        state, resolution = self.manager.apply_damage(
            combat_id,
            ranger_id,
            damage_amount=5,
            source_id=wizard_id,
            rng=RandSequence([6]),
        )
        self.assertEqual(resolution.application.damage_dealt, 5)

    def test_hunters_mark_no_bonus_wrong_attacker(self) -> None:
        extra = _wizard(name="Charlie")
        self.char_repo.save(extra)
        state = self.manager.create_combat(
            "guild1", "channel1", [self.ranger.id, self.wizard.id, extra.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([14, 10, 6]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        ranger_id = id_map[self.ranger.id]
        wizard_id = id_map[self.wizard.id]
        charlie_id = id_map[extra.id]
        combat_id = int(state.combat_id)

        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)
        _, resolution = self.manager.apply_damage(
            combat_id,
            wizard_id,
            damage_amount=5,
            source_id=charlie_id,
            rng=RandSequence([6]),
        )
        self.assertEqual(resolution.application.damage_dealt, 5)

    def test_concentration_break_clears_hunters_mark_overlay(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)

        state, _ = self.manager.apply_damage(
            combat_id,
            ranger_id,
            damage_amount=22,
            source_id=wizard_id,
            rng=RandSequence([3]),
        )
        self.assertIsNone(state.combatants[ranger_id].concentration_spell_id)
        self.assertIsNone(state.combatants[wizard_id].hunters_mark_caster_id)

    def test_recast_hunters_mark_clears_previous_target_mark(self) -> None:
        extra = _wizard(name="Charlie")
        self.char_repo.save(extra)
        state = self.manager.create_combat(
            "guild1", "channel1", [self.ranger.id, self.wizard.id, extra.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([14, 10, 6]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        ranger_id = id_map[self.ranger.id]
        wizard_id = id_map[self.wizard.id]
        charlie_id = id_map[extra.id]
        combat_id = int(state.combat_id)

        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)
        for _ in range(3):
            self.manager.advance_turn(combat_id)
        state = self.manager.cast_hunters_mark(combat_id, ranger_id, charlie_id)
        self.assertIsNone(state.combatants[wizard_id].hunters_mark_caster_id)
        self.assertEqual(state.combatants[charlie_id].hunters_mark_caster_id, ranger_id)


if __name__ == "__main__":
    unittest.main()
