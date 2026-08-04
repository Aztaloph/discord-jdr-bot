# tests/unit/test_combat_service.py
"""Lot C7 — CombatService, journal événementiel, round-trip persistance."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.combat_service import CombatService
from jdr_engine.core.events.combat_events import (
    ConditionApplied,
    SpellCast,
)
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
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


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _wizard(*, name: str = "Mage") -> Character:
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


class TestCombatService(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.ranger = _ranger(name="Alice")
        self.wizard = _wizard(name="Bob")
        self.char_repo.save(self.ranger)
        self.char_repo.save(self.wizard)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _service(self) -> CombatService:
        return CombatService.from_db_path(self.db_path, self.engine)

    def _active_fight(self, service: CombatService) -> tuple[int, str, str]:
        state = service.create_combat(
            "guild1", "channel1", [self.ranger.id, self.wizard.id]
        )
        state = service.activate_combat(
            int(state.combat_id), rng=InitiativeSequence([10, 8])
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
        return int(state.combat_id), ranger_id, wizard_id

    def test_round_trip_conditions_and_concentration(self) -> None:
        service = self._service()
        combat_id, ranger_id, wizard_id = self._active_fight(service)

        service.apply_condition(combat_id, wizard_id, "poisoned")
        service.cast_hunters_mark(combat_id, ranger_id, wizard_id)
        service.apply_damage(
            combat_id,
            wizard_id,
            damage_amount=5,
            source_id=ranger_id,
        )

        reloaded_service = CombatService.from_db_path(self.db_path, self.engine)
        state = reloaded_service.load_combat(combat_id)
        wizard = state.combatants[wizard_id]
        ranger = state.combatants[ranger_id]

        self.assertIn("poisoned", wizard.conditions)
        self.assertEqual(ranger.concentration_spell_id, "hunters_mark")
        self.assertLess(wizard.hp_current, wizard.hp_max)

    def test_event_log_populated(self) -> None:
        service = self._service()
        combat_id, ranger_id, wizard_id = self._active_fight(service)
        service.apply_condition(combat_id, wizard_id, "frightened")
        service.cast_hunters_mark(combat_id, ranger_id, wizard_id)

        log = service.get_event_log(combat_id)
        event_types = [entry.event_type for entry in log]
        self.assertIn("CombatStarted", event_types)
        self.assertIn("ConditionApplied", event_types)
        self.assertIn("SpellCast", event_types)

        condition_entries = [
            entry for entry in log if entry.event_type == "ConditionApplied"
        ]
        self.assertEqual(condition_entries[-1].payload["condition_id"], "frightened")

    def test_load_open_combat_via_new_service_instance(self) -> None:
        service = self._service()
        combat_id, _, _ = self._active_fight(service)

        other = CombatService.from_db_path(self.db_path, self.engine)
        loaded = other.load_open_combat("guild1", "channel1")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(int(loaded.combat_id), combat_id)
        self.assertEqual(loaded.status, "active")


if __name__ == "__main__":
    unittest.main()
