# tests/integration/test_character_lifecycle.py
"""Cycle de vie complet : migration → fiche calculée."""
import json
import tempfile
import unittest
from pathlib import Path

from jdr_engine.application import (
    CharacterService,
    GetCharacterSheetQuery,
)
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.persistence.character_repository import JsonCharacterRepository
from jdr_engine.persistence.migrations.v1_to_v2 import migrate_v1_to_v2
from jdr_engine.rules import RuleEngine

V1_SAMPLE = {
    "characters": {
        "7fcf37cd": {
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
    }
}


class TestCharacterLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_migrated_aztaloph_sheet_coherent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            v1 = tmp_path / "v1.json"
            v2 = tmp_path / "v2.json"
            v1.write_text(json.dumps(V1_SAMPLE), encoding="utf-8")
            repo = JsonCharacterRepository(v2)
            migrate_v1_to_v2(v1_path=v1, v2_repo=repo, backup=False)

            service = CharacterService(repo, self.engine)
            sheet = service.get_sheet(
                GetCharacterSheetQuery(
                    character_id="7fcf37cd",
                    owner_id="372519173097652236",
                    locale="fr",
                )
            )
            # elf +2 DEX → 12, mod +1 ; fighter d10 ; CON 10 → HP 10 (pas 100)
            self.assertEqual(sheet.race_name, "Elfe")
            self.assertEqual(sheet.class_name, "Guerrier")
            self.assertEqual(sheet.ability_scores["dex"], 12)
            self.assertEqual(sheet.hp_max, 10)
            self.assertEqual(sheet.proficiency_bonus, 2)
            self.assertNotEqual(sheet.hp_max, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
