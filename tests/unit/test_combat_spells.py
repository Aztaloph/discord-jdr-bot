# tests/unit/test_combat_spells.py
"""Lot C3b — sorts en combat (attaque, sauvegarde, hunters_mark, bless)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import (
    AttackRollResolved,
    DamageDealt,
    SavingThrowResolved,
    SpellCast,
)
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.saving_throw import damage_after_save


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


def _wizard(*, name: str = "Mage", hp: int = 20) -> Character:
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
                "spells_prepared": ["burning_hands", "magic_missile"],
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
                "dex": 16,
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


def _cleric(*, name: str = "Clerc") -> Character:
    return Character(
        owner_id="113",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="cleric",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 10,
                "dex": 10,
                "con": 12,
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


class TestSavingThrowRules(unittest.TestCase):
    def test_half_damage_on_successful_save(self) -> None:
        self.assertEqual(
            damage_after_save(11, save_succeeded_flag=True, half_on_save=True),
            5,
        )
        self.assertEqual(
            damage_after_save(11, save_succeeded_flag=False, half_on_save=True),
            11,
        )


class TestCombatSpells(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        for event_type in (
            SpellCast,
            AttackRollResolved,
            SavingThrowResolved,
            DamageDealt,
        ):
            self.bus.subscribe(event_type, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.wizard = _wizard(name="Alice")
        self.target = _wizard(name="Bob", hp=30)
        self.ranger = _ranger()
        self.cleric = _cleric()
        for char in (self.wizard, self.target, self.ranger, self.cleric):
            self.char_repo.save(char)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _active_two(
        self, *character_ids: str
    ) -> tuple[int, dict[str, str]]:
        state = self.manager.create_combat("guild1", "channel1", list(character_ids))
        state = self.manager.activate_combat(
            int(state.combat_id), rng=InitiativeSequence([12, 8])
        )
        id_map = {
            c.character_id: cid for cid, c in state.combatants.items()
        }
        return int(state.combat_id), id_map

    def test_fire_bolt_spell_attack_hit(self) -> None:
        combat_id, ids = self._active_two(self.wizard.id, self.target.id)
        caster_id = ids[self.wizard.id]
        target_id = ids[self.target.id]
        hp_before = self.manager.load_combat(combat_id).combatants[target_id].hp_current

        state, outcome = self.manager.cast_spell_attack(
            combat_id,
            caster_id,
            target_id,
            "fire_bolt",
            rng=RandSequence([15, 7]),
        )
        self.assertTrue(outcome.attack.outcome.hit)
        self.assertIsNotNone(outcome.damage)
        assert outcome.damage is not None
        self.assertEqual(
            state.combatants[target_id].hp_current,
            hp_before - outcome.damage.application.damage_dealt,
        )
        self.assertIsInstance(self.events[0], SpellCast)

    def test_fire_bolt_natural_1_misses_without_damage(self) -> None:
        combat_id, ids = self._active_two(self.wizard.id, self.target.id)
        caster_id = ids[self.wizard.id]
        target_id = ids[self.target.id]
        hp_before = self.manager.load_combat(combat_id).combatants[target_id].hp_current

        _state, outcome = self.manager.cast_spell_attack(
            combat_id,
            caster_id,
            target_id,
            "fire_bolt",
            rng=RandSequence([1]),
        )
        self.assertTrue(outcome.attack.outcome.automatic_miss)
        self.assertIsNone(outcome.damage)
        loaded = self.manager.load_combat(combat_id)
        self.assertEqual(loaded.combatants[target_id].hp_current, hp_before)

    def test_burning_hands_half_damage_on_save(self) -> None:
        combat_id, ids = self._active_two(self.wizard.id, self.target.id)
        caster_id = ids[self.wizard.id]
        target_id = ids[self.target.id]

        _state, outcome = self.manager.cast_spell_save(
            combat_id,
            caster_id,
            target_id,
            "burning_hands",
            rng=RandSequence([4, 5, 6, 12]),
        )
        self.assertTrue(outcome.succeeded)
        self.assertEqual(outcome.damage_roll.total, 15)
        self.assertEqual(outcome.damage.application.damage_dealt, 7)
        save_events = [e for e in self.events if isinstance(e, SavingThrowResolved)]
        self.assertEqual(len(save_events), 1)

    def test_hunters_mark_concentration_and_mark_persist(self) -> None:
        combat_id, ids = self._active_two(self.ranger.id, self.target.id)
        caster_id = ids[self.ranger.id]
        target_id = ids[self.target.id]

        state = self.manager.cast_hunters_mark(combat_id, caster_id, target_id)
        self.assertEqual(
            state.combatants[caster_id].concentration_spell_id, "hunters_mark"
        )
        self.assertEqual(state.combatants[target_id].hunters_mark_caster_id, caster_id)

        loaded = self.manager.load_combat(combat_id)
        self.assertEqual(
            loaded.combatants[caster_id].concentration_spell_id, "hunters_mark"
        )
        self.assertEqual(
            loaded.combatants[target_id].hunters_mark_caster_id, caster_id
        )

    def test_bless_three_targets_persist(self) -> None:
        extra = _wizard(name="Charlie", hp=18)
        self.char_repo.save(extra)
        state = self.manager.create_combat(
            "guild1",
            "channel1",
            [self.cleric.id, self.target.id, extra.id],
        )
        state = self.manager.activate_combat(
            int(state.combat_id), rng=InitiativeSequence([14, 10, 6])
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        caster_id = id_map[self.cleric.id]
        target_ids = [id_map[self.target.id], id_map[extra.id]]

        state = self.manager.cast_bless(int(state.combat_id), caster_id, target_ids)
        self.assertEqual(state.combatants[caster_id].concentration_spell_id, "bless")
        for tid in target_ids:
            self.assertTrue(state.combatants[tid].blessed)

        loaded = self.manager.load_combat(int(state.combat_id))
        for tid in target_ids:
            self.assertTrue(loaded.combatants[tid].blessed)


if __name__ == "__main__":
    unittest.main()
