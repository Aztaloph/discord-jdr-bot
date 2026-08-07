# tests/unit/test_api_v1_combat.py
"""Lot API v1 — cycle de vie combat, invariant lobby, parcours E2E §5.1."""
from __future__ import annotations

import copy
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
from jdr_engine.application.combat_service import CombatService
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


def _fighter(*, char_id: str, name: str, dex: int = 12) -> Character:
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
                "dex": dex,
                "con": 14,
                "int": 10,
                "wis": 10,
                "cha": 8,
            }
        ),
        hp_current=12,
        hp_max=12,
    )


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

    def __call__(self, low: int, high: int) -> int:
        if not self._values:
            raise RuntimeError("RandSequence épuisé")
        return self._values.pop(0)


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


class TestApiV1CombatE2E(unittest.TestCase):
    """Parcours contractuel §5.1 — bout en bout."""

    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="e2e_alice", name="Alice", dex=14)
        self.bob = _fighter(char_id="e2e_bob", name="Bob", dex=10)
        for char in (self.alice, self.bob):
            self.repo.save(char)
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_initiative_rng=InitiativeSequence([15, 8]),
                combat_attack_rng=RandSequence([14]),
            )
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_contract_parcours_7_etapes(self):
        # 1. Fiche initiale
        sheet_before = self.client.get(f"/v1/characters/{self.alice.id}/sheet")
        self.assertEqual(sheet_before.status_code, 200)
        self.assertNotIn("active_effects", sheet_before.json())
        self.assertEqual(sheet_before.json()["hp_current"], 12)

        # 2. Créer le lobby
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "e2e-parcours",
            },
        )
        self.assertEqual(created.status_code, 200)
        combat_id = created.json()["combat_id"]

        # 3. Activer
        activated = self.client.post(f"/v1/combats/{combat_id}/activate")
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["status"], "active")
        active_id = activated.json()["initiative_order"][
            activated.json()["turn_index"]
        ]
        target_id = next(
            cid
            for cid in activated.json()["combatants"]
            if cid != active_id
        )

        # 4. Jet d'attaque
        attack = self.client.post(
            f"/v1/combats/{combat_id}/attack-roll",
            json={
                "attacker_id": active_id,
                "target_id": target_id,
                "melee_weapon": True,
                "ranged_weapon": False,
            },
        )
        self.assertEqual(attack.status_code, 200)
        self.assertIn("d20", attack.json())
        self.assertIn("outcome", attack.json())

        # 5. État rencontre
        combat = self.client.get(f"/v1/combats/{combat_id}")
        self.assertEqual(combat.status_code, 200)
        self.assertEqual(combat.json()["status"], "active")

        # 6. Fiche fusionnée
        sheet_merged = self.client.get(f"/v1/characters/{self.alice.id}/sheet")
        self.assertEqual(sheet_merged.status_code, 200)
        self.assertIn("active_effects", sheet_merged.json())
        self.assertIsInstance(sheet_merged.json()["active_effects"], list)

        # 7. Clôture
        closed = self.client.post(f"/v1/combats/{combat_id}/close")
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], "ended")

        sheet_after = self.client.get(f"/v1/characters/{self.alice.id}/sheet")
        self.assertNotIn("active_effects", sheet_after.json())


class TestApiV1AttackRollAndMergedSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="atk_alice", name="Alice", dex=16)
        self.bob = _fighter(char_id="atk_bob", name="Bob", dex=10)
        for char in (self.alice, self.bob):
            self.repo.save(char)
        self.combat_service = CombatService.from_db_path(
            self.db_path,
            self.engine,
            register_auto_save_handler=False,
        )
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_initiative_rng=InitiativeSequence([18, 6]),
                combat_attack_rng=RandSequence([12]),
            )
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_attack_in_preparing_combat_rejected(self):
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "preparing-only",
            },
        )
        self.assertEqual(created.status_code, 200)
        combat_id = created.json()["combat_id"]
        attacker_id, target_id = list(created.json()["combatants"])

        response = self.client.post(
            f"/v1/combats/{combat_id}/attack-roll",
            json={
                "attacker_id": attacker_id,
                "target_id": target_id,
                "melee_weapon": True,
                "ranged_weapon": False,
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(_api_error(response)["code"], "COMBAT_STATUS_INVALID")

    def test_attack_does_not_persist_character_sheet(self):
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "persist-check",
            },
        )
        combat_id = created.json()["combat_id"]
        activated = self.client.post(f"/v1/combats/{combat_id}/activate")
        active_id = activated.json()["initiative_order"][
            activated.json()["turn_index"]
        ]
        target_id = next(
            cid for cid in activated.json()["combatants"] if cid != active_id
        )

        before = copy.deepcopy(self.repo.get_by_id(self.alice.id))
        response = self.client.post(
            f"/v1/combats/{combat_id}/attack-roll",
            json={
                "attacker_id": active_id,
                "target_id": target_id,
                "melee_weapon": True,
                "ranged_weapon": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        after = self.repo.get_by_id(self.alice.id)
        assert before is not None and after is not None
        self.assertEqual(after.hp_current, before.hp_current)
        self.assertEqual(after.to_dict(), before.to_dict())

    def test_merged_sheet_hp_overlay_without_sqlite_write(self):
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "merged-hp",
            },
        )
        combat_id = created.json()["combat_id"]
        self.client.post(f"/v1/combats/{combat_id}/activate")
        state = self.combat_service.load_combat(combat_id)
        bob_combatant_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.bob.id
        )
        sqlite_hp_before = self.repo.get_by_id(self.bob.id).hp_current

        self.combat_service.apply_damage(
            combat_id,
            bob_combatant_id,
            damage_amount=5,
        )

        sheet = self.client.get(f"/v1/characters/{self.bob.id}/sheet")
        self.assertEqual(sheet.status_code, 200)
        self.assertEqual(sheet.json()["hp_current"], sqlite_hp_before - 5)
        self.assertEqual(
            self.repo.get_by_id(self.bob.id).hp_current,
            sqlite_hp_before,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
