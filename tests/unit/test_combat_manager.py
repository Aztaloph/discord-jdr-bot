# tests/unit/test_combat_manager.py
"""Lot C1 — CombatManager, persistance combats, événements de cycle de vie."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import CombatEnded, CombatStarted
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.combat_state import (
    COMBAT_STATE_VERSION,
    CombatState,
    CombatStateVersionError,
)
from jdr_engine.game.combat_manager import (
    CombatCharacterNotFoundError,
    CombatManager,
)
from jdr_engine.persistence.combat_repository import (
    ActiveCombatExistsError,
    CombatNotFoundError,
    SqliteCombatRepository,
)
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _wizard(engine: RuleEngine, *, name: str = "Test Mage") -> Character:
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


class TestCombatManager(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.bus.subscribe(CombatStarted, self.events.append)
        self.bus.subscribe(CombatEnded, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.alice = _wizard(self.engine, name="Alice")
        self.bob = _wizard(self.engine, name="Bob")
        self.char_repo.save(self.alice)
        self.char_repo.save(self.bob)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_create_combat_persists_and_publishes_started(self) -> None:
        state = self.manager.create_combat(
            "guild1",
            "channel1",
            [self.alice.id, self.bob.id],
        )
        self.assertIsNotNone(state.combat_id)
        self.assertEqual(state.status, "active")
        self.assertEqual(state.schema_version, COMBAT_STATE_VERSION)
        self.assertEqual(len(state.combatants), 2)
        self.assertEqual(len(self.events), 1)
        started = self.events[0]
        self.assertIsInstance(started, CombatStarted)
        assert isinstance(started, CombatStarted)
        self.assertEqual(started.combat_id, state.combat_id)
        self.assertEqual(started.character_ids, (self.alice.id, self.bob.id))

        loaded = self.manager.load_combat(int(state.combat_id))
        self.assertEqual(loaded.combat_id, state.combat_id)
        self.assertEqual(len(loaded.combatants), 2)

    def test_load_active_by_channel(self) -> None:
        self.manager.create_combat("guild1", "channel1", [self.alice.id])
        active = self.manager.load_active_combat("guild1", "channel1")
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.status, "active")
        self.assertIsNone(self.manager.load_active_combat("guild1", "channel99"))

    def test_save_combat_updates_blob(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [self.alice.id])
        state.round_number = 2
        self.manager.save_combat(state)
        loaded = self.manager.load_combat(int(state.combat_id))
        self.assertEqual(loaded.round_number, 2)

    def test_close_combat_ends_and_publishes(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [self.alice.id])
        closed = self.manager.close_combat(int(state.combat_id), reason="test")
        self.assertEqual(closed.status, "ended")
        self.assertIsNotNone(closed.ended_at)
        self.assertIsInstance(self.events[-1], CombatEnded)
        self.assertIsNone(self.manager.load_active_combat("guild1", "channel1"))

    def test_second_active_combat_same_channel_rejected(self) -> None:
        self.manager.create_combat("guild1", "channel1", [self.alice.id])
        with self.assertRaises(ActiveCombatExistsError):
            self.manager.create_combat("guild1", "channel1", [self.bob.id])

    def test_new_combat_after_closed_allowed(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [self.alice.id])
        self.manager.close_combat(int(state.combat_id))
        state2 = self.manager.create_combat("guild1", "channel1", [self.bob.id])
        self.assertEqual(state2.status, "active")

    def test_parallel_channels_same_guild_allowed(self) -> None:
        self.manager.create_combat("guild1", "channel1", [self.alice.id])
        state2 = self.manager.create_combat("guild1", "channel2", [self.bob.id])
        self.assertEqual(state2.status, "active")

    def test_unknown_character_rejected(self) -> None:
        with self.assertRaises(CombatCharacterNotFoundError):
            self.manager.create_combat("guild1", "channel1", ["missing"])

    def test_load_missing_combat_raises(self) -> None:
        with self.assertRaises(CombatNotFoundError):
            self.manager.load_combat(9999)

    def test_unknown_blob_version_rejected(self) -> None:
        import sqlite3

        state = self.manager.create_combat("guild1", "channel1", [self.alice.id])
        record = self.combat_repo.get_by_id(int(state.combat_id))
        assert record is not None
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT state_json FROM combats WHERE id = ?", (record.combat_id,)
        ).fetchone()
        data = json.loads(row[0])
        data["schema_version"] = 99
        conn.execute(
            "UPDATE combats SET state_json = ? WHERE id = ?",
            (json.dumps(data), record.combat_id),
        )
        conn.commit()
        conn.close()
        with self.assertRaises(CombatStateVersionError):
            self.combat_repo.get_by_id(record.combat_id)

    def test_blob_does_not_contain_status(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [self.alice.id])
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT state_json FROM combats WHERE id = ?",
            (int(state.combat_id),),
        ).fetchone()
        conn.close()
        data = json.loads(row[0])
        self.assertNotIn("status", data)

    def test_legacy_blob_status_ignored_uses_sql_column(self) -> None:
        import sqlite3

        state = self.manager.create_combat("guild1", "channel1", [self.alice.id])
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT state_json FROM combats WHERE id = ?",
            (int(state.combat_id),),
        ).fetchone()
        data = json.loads(row[0])
        data["status"] = "ended"
        conn.execute(
            "UPDATE combats SET state_json = ? WHERE id = ?",
            (json.dumps(data), int(state.combat_id)),
        )
        conn.commit()
        conn.close()
        loaded = self.manager.load_combat(int(state.combat_id))
        self.assertEqual(loaded.status, "active")

    def test_empty_character_list_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.create_combat("guild1", "channel1", [])


if __name__ == "__main__":
    unittest.main()
