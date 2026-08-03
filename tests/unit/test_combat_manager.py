# tests/unit/test_combat_manager.py
"""Lots C1–C2 — CombatManager, persistance, initiative et tours."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import (
    CombatEnded,
    CombatStarted,
    InitiativeRolled,
    RoundStarted,
    TurnEnded,
    TurnStarted,
)
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
    CombatStatusError,
    InsufficientCombatantsError,
    NoActiveCombatantsError,
)
from jdr_engine.persistence.combat_repository import (
    ActiveCombatExistsError,
    CombatNotFoundError,
    SqliteCombatRepository,
)
from jdr_engine.persistence.database import (
    DB_SCHEMA_VERSION,
    ensure_combats_schema,
    init_database,
)
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine


class SequenceRng:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self) -> int:
        if not self._values:
            raise RuntimeError("SequenceRng épuisé")
        return self._values.pop(0)


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _wizard(
    engine: RuleEngine,
    *,
    name: str = "Test Mage",
    dex: int = 14,
) -> Character:
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


class TestCombatManager(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        for event_type in (
            CombatStarted,
            CombatEnded,
            InitiativeRolled,
            TurnStarted,
            TurnEnded,
            RoundStarted,
        ):
            self.bus.subscribe(event_type, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.alice = _wizard(self.engine, name="Alice", dex=16)
        self.bob = _wizard(self.engine, name="Bob", dex=10)
        self.char_repo.save(self.alice)
        self.char_repo.save(self.bob)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _create_and_activate(
        self,
        guild: str = "guild1",
        channel: str = "channel1",
        *,
        rng: SequenceRng | None = None,
    ) -> CombatState:
        state = self.manager.create_combat(guild, channel, [self.alice.id, self.bob.id])
        return self.manager.activate_combat(
            int(state.combat_id),
            rng=rng or SequenceRng([15, 10]),
        )

    def test_create_combat_starts_preparing(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [self.alice.id])
        self.assertIsNotNone(state.combat_id)
        self.assertEqual(state.status, "preparing")
        self.assertEqual(state.round_number, 0)
        self.assertEqual(state.initiative_order, ())
        self.assertEqual(len(self.events), 1)
        started = self.events[0]
        self.assertIsInstance(started, CombatStarted)

    def test_create_empty_combat_allowed(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [])
        self.assertEqual(state.status, "preparing")
        self.assertEqual(len(state.combatants), 0)

    def test_add_combatant_during_preparing(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [])
        updated = self.manager.add_combatant(int(state.combat_id), self.alice.id)
        self.assertEqual(len(updated.combatants), 1)
        updated = self.manager.add_combatant(int(state.combat_id), self.bob.id)
        self.assertEqual(len(updated.combatants), 2)

    def test_activate_requires_two_combatants(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [self.alice.id])
        with self.assertRaises(InsufficientCombatantsError):
            self.manager.activate_combat(int(state.combat_id), rng=SequenceRng([10]))

    def test_activate_rolls_initiative_and_starts_turn(self) -> None:
        state = self._create_and_activate(rng=SequenceRng([18, 5]))
        self.assertEqual(state.status, "active")
        self.assertEqual(state.round_number, 1)
        self.assertEqual(state.turn_index, 0)
        self.assertEqual(len(state.initiative_order), 2)
        initiative_events = [e for e in self.events if isinstance(e, InitiativeRolled)]
        turn_events = [e for e in self.events if isinstance(e, TurnStarted)]
        self.assertEqual(len(initiative_events), 1)
        self.assertGreaterEqual(len(turn_events), 1)
        first_turn = turn_events[-1]
        self.assertEqual(first_turn.combatant_id, state.initiative_order[0])

    def test_advance_turn_and_round(self) -> None:
        state = self._create_and_activate(rng=SequenceRng([12, 8]))
        first = state.initiative_order[state.turn_index]
        state = self.manager.advance_turn(int(state.combat_id))
        self.assertNotEqual(state.initiative_order[state.turn_index], first)
        state = self.manager.advance_turn(int(state.combat_id))
        self.assertEqual(state.round_number, 2)
        self.assertEqual(state.turn_index, 0)
        round_events = [e for e in self.events if isinstance(e, RoundStarted)]
        self.assertEqual(len(round_events), 1)

    def test_remove_combatant_skips_turn(self) -> None:
        state = self._create_and_activate(rng=SequenceRng([14, 14]))
        order = state.initiative_order
        removed_id = order[0]
        self.manager.remove_combatant(int(state.combat_id), removed_id)
        state = self.manager.advance_turn(int(state.combat_id))
        self.assertEqual(state.initiative_order[state.turn_index], order[1])

    def test_remove_all_active_raises_on_advance(self) -> None:
        state = self._create_and_activate(rng=SequenceRng([10, 12]))
        for cid in state.initiative_order:
            self.manager.remove_combatant(int(state.combat_id), cid)
        with self.assertRaises(NoActiveCombatantsError):
            self.manager.advance_turn(int(state.combat_id))

    def test_turn_progression_survives_save_reload(self) -> None:
        state = self._create_and_activate(rng=SequenceRng([16, 7]))
        self.manager.advance_turn(int(state.combat_id))
        record = self.combat_repo.get_by_id(int(state.combat_id))
        assert record is not None
        snapshot = (
            record.state.round_number,
            record.state.turn_index,
            record.state.initiative_order,
        )
        loaded = self.manager.load_combat(int(state.combat_id))
        self.assertEqual(
            (loaded.round_number, loaded.turn_index, loaded.initiative_order),
            snapshot,
        )

    def test_load_open_by_channel(self) -> None:
        self.manager.create_combat("guild1", "channel1", [self.alice.id])
        open_state = self.manager.load_open_combat("guild1", "channel1")
        self.assertIsNotNone(open_state)
        assert open_state is not None
        self.assertEqual(open_state.status, "preparing")
        self.assertIsNone(self.manager.load_open_combat("guild1", "channel99"))

    def test_save_combat_updates_blob(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [self.alice.id, self.bob.id])
        state.round_number = 99
        self.manager.save_combat(state)
        loaded = self.manager.load_combat(int(state.combat_id))
        self.assertEqual(loaded.round_number, 99)

    def test_close_combat_ends_and_publishes(self) -> None:
        state = self._create_and_activate()
        closed = self.manager.close_combat(int(state.combat_id), reason="test")
        self.assertEqual(closed.status, "ended")
        self.assertIsNotNone(closed.ended_at)
        self.assertIsInstance(self.events[-1], CombatEnded)
        self.assertIsNone(self.manager.load_open_combat("guild1", "channel1"))

    def test_second_open_combat_same_channel_rejected(self) -> None:
        self.manager.create_combat("guild1", "channel1", [self.alice.id])
        with self.assertRaises(ActiveCombatExistsError):
            self.manager.create_combat("guild1", "channel1", [self.bob.id])

    def test_new_combat_after_closed_allowed(self) -> None:
        state = self.manager.create_combat("guild1", "channel1", [self.alice.id])
        self.manager.close_combat(int(state.combat_id))
        state2 = self.manager.create_combat("guild1", "channel1", [self.bob.id])
        self.assertEqual(state2.status, "preparing")

    def test_parallel_channels_same_guild_allowed(self) -> None:
        self.manager.create_combat("guild1", "channel1", [self.alice.id])
        state2 = self.manager.create_combat("guild1", "channel2", [self.bob.id])
        self.assertEqual(state2.status, "preparing")

    def test_add_combatant_rejected_when_active(self) -> None:
        state = self._create_and_activate()
        with self.assertRaises(CombatStatusError):
            self.manager.add_combatant(int(state.combat_id), self.alice.id)

    def test_unknown_character_rejected(self) -> None:
        with self.assertRaises(CombatCharacterNotFoundError):
            self.manager.create_combat("guild1", "channel1", ["missing"])

    def test_load_missing_combat_raises(self) -> None:
        with self.assertRaises(CombatNotFoundError):
            self.manager.load_combat(9999)

    def test_unknown_blob_version_rejected(self) -> None:
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
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT state_json FROM combats WHERE id = ?",
            (int(state.combat_id),),
        ).fetchone()
        conn.close()
        data = json.loads(row[0])
        self.assertNotIn("status", data)

    def test_legacy_blob_status_ignored_uses_sql_column(self) -> None:
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
        self.assertEqual(loaded.status, "preparing")

    def test_schema_migration_v2_to_v3(self) -> None:
        legacy_path = Path(self._tmpdir.name) / "legacy.db"
        conn = sqlite3.connect(legacy_path)
        conn.executescript(
            """
            CREATE TABLE combats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'ended')),
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX idx_combats_active_channel
                ON combats (guild_id, channel_id)
                WHERE status = 'active';
            INSERT INTO combats (guild_id, channel_id, status, state_json, updated_at)
            VALUES ('g1', 'c1', 'active', '{"schema_version":1}', 'now');
            """
        )
        conn.commit()
        conn.close()

        ensure_combats_schema(legacy_path)
        conn = sqlite3.connect(legacy_path)
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'combats'"
        ).fetchone()[0]
        index_names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'combats'"
            ).fetchall()
        ]
        row = conn.execute("SELECT status FROM combats WHERE id = 1").fetchone()
        conn.close()

        self.assertIn("'preparing'", table_sql)
        self.assertIn("idx_combats_open_channel", index_names)
        self.assertNotIn("idx_combats_active_channel", index_names)
        self.assertEqual(row[0], "active")

        repo = SqliteCombatRepository(legacy_path)
        meta_conn = sqlite3.connect(legacy_path)
        meta_conn.row_factory = sqlite3.Row
        version = meta_conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        meta_conn.close()
        self.assertIsNotNone(version)
        self.assertEqual(int(version["value"]), DB_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
