# tests/unit/test_character_service.py
import tempfile
import unittest
from pathlib import Path

from jdr_engine.application import (
    CharacterNotFoundError,
    CharacterService,
    CharacterValidationError,
    CreateCharacterCommand,
    GetCharacterSheetQuery,
    ListCharactersQuery,
)
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.persistence.character_repository import JsonCharacterRepository
from jdr_engine.rules import RuleEngine


class TestCharacterService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = JsonCharacterRepository(
            Path(self.tmp.name) / "characters.json"
        )
        self.service = CharacterService(self.repo, self.engine)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_get_sheet(self):
        char = self.service.create(
            CreateCharacterCommand(
                owner_id="42",
                name="Aldric",
                race_id="elf",
                class_id="fighter",
                level=1,
            )
        )
        sheet = self.service.get_sheet(
            GetCharacterSheetQuery(character_id=char.id, owner_id="42")
        )
        self.assertEqual(sheet.name, "Aldric")
        self.assertEqual(sheet.race_id, "elf")
        self.assertEqual(sheet.class_id, "fighter")
        self.assertEqual(sheet.hp_max, 10)  # d10 + CON 0

    def test_duplicate_name_rejected(self):
        self.service.create(
            CreateCharacterCommand(
                owner_id="42",
                name="Dup",
                race_id="human",
                class_id="fighter",
            )
        )
        with self.assertRaises(CharacterValidationError):
            self.service.create(
                CreateCharacterCommand(
                    owner_id="42",
                    name="Dup",
                    race_id="dwarf",
                    class_id="wizard",
                )
            )

    def test_unknown_race_rejected(self):
        with self.assertRaises(CharacterValidationError):
            self.service.create(
                CreateCharacterCommand(
                    owner_id="1",
                    name="X",
                    race_id="orc",
                    class_id="fighter",
                )
            )

    def test_list_by_owner(self):
        self.service.create(
            CreateCharacterCommand(
                owner_id="99",
                name="A",
                race_id="human",
                class_id="fighter",
            )
        )
        self.service.create(
            CreateCharacterCommand(
                owner_id="99",
                name="B",
                race_id="dwarf",
                class_id="cleric",
            )
        )
        chars = self.service.list_by_owner(ListCharactersQuery(owner_id="99"))
        self.assertEqual(len(chars), 2)

    def test_not_found(self):
        with self.assertRaises(CharacterNotFoundError):
            self.service.get_sheet(
                GetCharacterSheetQuery(name="ghost", owner_id="1")
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
