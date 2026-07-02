# tests/unit/test_migration_v1_v2.py
import json
import tempfile
import unittest
from pathlib import Path

from jdr_engine.domain.character import Character
from jdr_engine.persistence.character_repository import JsonCharacterRepository
from jdr_engine.persistence.migrations.v1_to_v2 import convert_v1_record, migrate_v1_to_v2

V1_AZTALOPH = {
    "owner_id": 372519173097652236,
    "nom": "aztaloph",
    "race": "Elfe",
    "classe": "Guerrier",
    "niveau": 1,
    "id": "7fcf37cd",
    "image_url": None,
    "caracteristiques": {
        "force": 10,
        "dexterite": 10,
        "constitution": 10,
        "intelligence": 10,
        "sagesse": 10,
        "charisme": 10,
    },
    "pv_max": 100,
    "pv_actuels": 100,
    "ca": 20,
    "bonus_maitrise": 2,
    "attaques": [],
}


class TestMigrationV1V2(unittest.TestCase):
    def test_convert_aztaloph(self):
        char = convert_v1_record(V1_AZTALOPH)
        self.assertEqual(char.id, "7fcf37cd")
        self.assertEqual(char.name, "aztaloph")
        self.assertEqual(char.race_id, "elf")
        self.assertEqual(char.class_id, "fighter")
        self.assertEqual(char.ability_scores.get("dex"), 10)

    def test_migrate_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            v1 = tmp_path / "v1.json"
            v2 = tmp_path / "v2.json"
            v1.write_text(
                json.dumps({"characters": {"7fcf37cd": V1_AZTALOPH}}),
                encoding="utf-8",
            )
            repo = JsonCharacterRepository(v2)
            migrated = migrate_v1_to_v2(
                v1_path=v1,
                v2_repo=repo,
                backup=False,
            )
            self.assertEqual(len(migrated), 1)
            loaded = repo.get_by_id("7fcf37cd")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.race_id, "elf")


if __name__ == "__main__":
    unittest.main(verbosity=2)
