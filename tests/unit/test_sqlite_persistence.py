# tests/unit/test_sqlite_persistence.py
"""Stockage SQLite — migration, CRUD, moteur de sorts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import (
    init_database,
    migrate_json_v2_to_sqlite,
    run_startup_migrations,
)
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting import cast_spell


MARIE = {
    "id": "marie001",
    "owner_id": "999001",
    "guild_id": "111",
    "name": "Marie la prêtresse",
    "race_id": "human",
    "class_id": "cleric",
    "level": 3,
    "ability_scores": {"str": 10, "dex": 12, "con": 14, "int": 10, "wis": 16, "cha": 12},
    "hp_current": 18,
    "hp_max": 24,
    "choices": {
        "spellcasting": {
            "cantrips_known": ["sacred_flame"],
            "spells_prepared": ["cure_wounds"],
            "slots_used": {},
        }
    },
}

JOE = {
    "id": "joe00001",
    "owner_id": "999001",
    "guild_id": "111",
    "name": "Joe le mage",
    "race_id": "human",
    "class_id": "wizard",
    "level": 3,
    "ability_scores": {"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
    "hp_current": 20,
    "choices": {
        "spellcasting": {
            "cantrips_known": ["fire_bolt"],
            "spells_prepared": ["fire_bolt", "burning_hands"],
            "slots_used": {},
        }
    },
}


class TestSqlitePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "bot.db"
        init_database(self.db_path)
        self.repo = SqliteCharacterRepository(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_load_roundtrip(self):
        char = Character.from_dict(MARIE)
        self.repo.save(char)
        loaded = self.repo.get_by_name("Marie la prêtresse", "999001")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.class_id, "cleric")
        self.assertEqual(loaded.hp_max, 24)
        self.assertEqual(loaded.ability_scores.get("wis"), 16)

    def test_migrate_json_v2(self):
        json_path = Path(self.tmp.name) / "characters.json"
        json_path.write_text(
            json.dumps({"characters": {"marie001": MARIE, "joe00001": JOE}}),
            encoding="utf-8",
        )
        from jdr_engine.persistence.database import get_connection

        with get_connection(self.db_path) as conn:
            count = migrate_json_v2_to_sqlite(
                conn, json_path=json_path, default_guild_id="111"
            )
        self.assertEqual(count, 2)
        names = {c.name for c in self.repo.list_by_owner("999001")}
        self.assertEqual(names, {"Joe le mage", "Marie la prêtresse"})

    def test_spell_cast_persists_slots_in_sqlite(self):
        if not Path("compendium/dnd5e").is_dir():
            self.skipTest("compendium absent")
        engine = RuleEngine.load("dnd5e", strict=False)
        char = Character.from_dict(JOE)
        self.repo.save(char)
        result = cast_spell(char, "burning_hands", engine, persist_slots=True)
        self.assertIsNotNone(result.updated_character)
        self.repo.save(result.updated_character)
        reloaded = self.repo.get_by_id("joe00001")
        self.assertIsNotNone(reloaded)
        slots = reloaded.choices["spellcasting"]["slots_used"]
        self.assertEqual(int(slots.get("1", slots.get(1, 0))), 1)


class TestStartupMigration(unittest.TestCase):
    def test_run_startup_migrations_creates_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            path = run_startup_migrations(db, default_guild_id="0")
            self.assertTrue(path.is_file())

    def test_deleted_character_not_reimported_on_restart(self):
        """Suppression définitive : le redémarrage ne réimporte pas le JSON."""
        char_data = {
            "id": "abc12345",
            "owner_id": "42",
            "guild_id": "100",
            "name": "Fantôme",
            "race_id": "human",
            "class_id": "wizard",
            "level": 1,
            "ability_scores": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        }
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            json_path = Path(tmp) / "characters.json"
            json_path.write_text(
                json.dumps({"characters": {"abc12345": char_data}}),
                encoding="utf-8",
            )
            run_startup_migrations(db, default_guild_id="100", json_path=json_path)
            repo = SqliteCharacterRepository(db)
            self.assertIsNotNone(repo.get_by_id("abc12345"))

            repo.delete("abc12345")
            self.assertIsNone(repo.get_by_id("abc12345"))

            run_startup_migrations(db, default_guild_id="100", json_path=json_path)
            self.assertIsNone(repo.get_by_id("abc12345"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
