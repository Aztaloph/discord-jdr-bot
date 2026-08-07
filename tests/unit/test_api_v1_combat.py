# tests/unit/test_api_v1_combat.py
"""Lot API v1 commit 3 — cycle de vie combat, invariant lobby, libération après close."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.api.app import create_app
from interfaces.api.combat_scope import (
    GENERATED_CHANNEL_ID_PREFIX,
    resolve_create_scope,
)
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine


def _api_error(response) -> dict:
    payload = response.json()
    assert "error" in payload, payload
    return payload["error"]


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _fighter(*, char_id: str, name: str) -> Character:
    return Character(
        id=char_id,
        owner_id="1",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="fighter",
        level=1,
        ability_scores=AbilityScores(
            scores={
                "str": 16,
                "dex": 12,
                "con": 14,
                "int": 10,
                "wis": 10,
                "cha": 8,
            }
        ),
        hp_current=12,
        hp_max=12,
    )


class TestCombatScope(unittest.TestCase):
    def test_generated_channel_id_uses_prefix(self):
        _guild, channel = resolve_create_scope(guild_id=None, channel_id=None)
        self.assertTrue(channel.startswith(GENERATED_CHANNEL_ID_PREFIX))

    def test_client_channel_id_unchanged(self):
        _guild, channel = resolve_create_scope(
            guild_id=None,
            channel_id="session-alpha",
        )
        self.assertEqual(channel, "session-alpha")

    def test_generated_id_does_not_collide_with_client_prefix_choice(self):
        client_channel = f"{GENERATED_CHANNEL_ID_PREFIX}manual"
        _guild, generated = resolve_create_scope(guild_id=None, channel_id=None)
        self.assertNotEqual(client_channel, generated)


class TestApiV1CombatLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="cmb_alice", name="Alice")
        self.bob = _fighter(char_id="cmb_bob", name="Bob")
        self.carol = _fighter(char_id="cmb_carol", name="Carol")
        for char in (self.alice, self.bob, self.carol):
            self.repo.save(char)
        self.client = TestClient(
            create_app(engine=self.engine, db_path=self.db_path)
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _count_combats(self) -> int:
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM combats").fetchone()[0]
        conn.close()
        return int(count)

    def _count_open_combats(self) -> int:
        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM combats WHERE status IN ('preparing', 'active')"
        ).fetchone()[0]
        conn.close()
        return int(count)

    def _create_combat(
        self,
        character_ids: list[str],
        *,
        channel_id: str | None = "test-channel",
    ):
        body: dict = {"character_ids": character_ids}
        if channel_id is not None:
            body["channel_id"] = channel_id
        return self.client.post("/v1/combats", json=body)

    def test_create_get_activate_close_happy_path(self):
        created = self._create_combat([self.alice.id, self.bob.id])
        self.assertEqual(created.status_code, 200)
        combat_id = created.json()["combat_id"]
        self.assertEqual(created.json()["status"], "preparing")
        self.assertEqual(len(created.json()["combatants"]), 2)

        fetched = self.client.get(f"/v1/combats/{combat_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["combat_id"], combat_id)

        activated = self.client.post(f"/v1/combats/{combat_id}/activate")
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["status"], "active")
        self.assertEqual(len(activated.json()["initiative_order"]), 2)

        closed = self.client.post(f"/v1/combats/{combat_id}/close")
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], "ended")

    def test_characters_reusable_after_close(self):
        """Test explicite commit 3 — clôture libère les personnages pour un nouveau lobby."""
        first = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id="lobby-a",
        )
        self.assertEqual(first.status_code, 200)
        combat_id_1 = first.json()["combat_id"]

        close = self.client.post(f"/v1/combats/{combat_id_1}/close")
        self.assertEqual(close.status_code, 200)
        self.assertEqual(close.json()["status"], "ended")

        second = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id="lobby-b",
        )
        self.assertEqual(second.status_code, 200)
        combat_id_2 = second.json()["combat_id"]
        self.assertNotEqual(combat_id_1, combat_id_2)
        self.assertEqual(second.json()["status"], "preparing")
        self.assertEqual(len(second.json()["combatants"]), 2)

    def test_character_already_in_combat_rejects_entire_body(self):
        first = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id="engaged",
        )
        self.assertEqual(first.status_code, 200)
        combats_before = self._count_combats()
        open_before = self._count_open_combats()

        response = self._create_combat(
            [self.bob.id, self.carol.id],
            channel_id="new-lobby",
        )
        self.assertEqual(response.status_code, 409)
        err = _api_error(response)
        self.assertEqual(err["code"], "CHARACTER_ALREADY_IN_COMBAT")
        self.assertEqual(err["details"]["character_id"], self.bob.id)
        self.assertEqual(self._count_combats(), combats_before)
        self.assertEqual(self._count_open_combats(), open_before)

    def test_unknown_character_rejects_without_creating_combat(self):
        combats_before = self._count_combats()
        response = self._create_combat([self.alice.id, "inconnu"])
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_api_error(response)["code"], "CHARACTER_NOT_FOUND")
        self.assertEqual(self._count_combats(), combats_before)

    def test_activate_insufficient_combatants(self):
        created = self._create_combat([self.alice.id], channel_id="solo")
        self.assertEqual(created.status_code, 200)
        combat_id = created.json()["combat_id"]
        response = self.client.post(f"/v1/combats/{combat_id}/activate")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            _api_error(response)["code"],
            "INSUFFICIENT_COMBATANTS",
        )

    def test_combat_not_found(self):
        response = self.client.get("/v1/combats/99999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_api_error(response)["code"], "COMBAT_NOT_FOUND")

    def test_open_combat_exists_same_channel(self):
        first = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id="shared-scope",
        )
        self.assertEqual(first.status_code, 200)
        second = self._create_combat(
            [self.carol.id],
            channel_id="shared-scope",
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(_api_error(second)["code"], "OPEN_COMBAT_EXISTS")

    def test_generated_channel_id_allows_parallel_combats(self):
        first = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id=None,
        )
        second = self._create_combat(
            [self.carol.id],
            channel_id=None,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(
            first.json()["combat_id"],
            second.json()["combat_id"],
        )

        conn = sqlite3.connect(self.db_path)
        channels = [
            row[0]
            for row in conn.execute(
                "SELECT channel_id FROM combats ORDER BY id"
            ).fetchall()
        ]
        conn.close()
        self.assertEqual(len(channels), 2)
        for channel in channels:
            self.assertTrue(channel.startswith(GENERATED_CHANNEL_ID_PREFIX))
        self.assertNotEqual(channels[0], channels[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
