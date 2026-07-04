# tests/unit/test_active_character.py
"""Personnage actif — plusieurs persos, un seul actif en jeu."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import (
    CharacterService,
    CharacterValidationError,
)
from jdr_engine.application.dto.character_commands import ListCharactersQuery
from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS
from jdr_engine.dice import DiceError
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine

from tests.helpers.creation import cleric_creation_kwargs, wizard_creation_kwargs

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.handlers.dice import execute_roll, resolve_character_for_roll
from interfaces.discord.handlers.spell import execute_spell_cast
from interfaces.discord.settings import DiscordSettings


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestActiveCharacter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def _service(self, db_path: Path) -> CharacterService:
        init_database(db_path)
        return CharacterService(SqliteCharacterRepository(db_path), self.engine)

    def test_multiple_creation_on_same_guild(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            first = service.create_from_wizard(
                owner_id="1",
                guild_id="100",
                name="Mage",
                **wizard_creation_kwargs(),
            )
            service.create_from_wizard(
                owner_id="1",
                guild_id="100",
                name="Clerc",
                **cleric_creation_kwargs(),
            )
            on_guild = service.list_by_owner(
                ListCharactersQuery(owner_id="1", guild_id="100")
            )
            self.assertEqual(len(on_guild), 2)
            active = service.get_active_character("1", "100")
            self.assertIsNotNone(active)
            assert active is not None
            self.assertEqual(active.id, first.id)

    def test_set_active_character(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            service.create_from_wizard(
                owner_id="1",
                guild_id="100",
                name="Mage",
                **wizard_creation_kwargs(),
            )
            clerc = service.create_from_wizard(
                owner_id="1",
                guild_id="100",
                name="Clerc",
                **cleric_creation_kwargs(),
            )
            service.set_active_character("1", "100", clerc.id)
            active = service.get_active_character("1", "100")
            assert active is not None
            self.assertEqual(active.id, clerc.id)

    def test_duplicate_name_same_guild_still_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            service.create_from_wizard(
                owner_id="1",
                guild_id="100",
                name="Dup",
                **wizard_creation_kwargs(),
            )
            with self.assertRaises(CharacterValidationError):
                service.create_from_wizard(
                    owner_id="1",
                    guild_id="100",
                    name="Dup",
                    **cleric_creation_kwargs(),
                )


class TestActiveCharacterGameCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Path(self.tmp.name) / "bot.db"
        init_database(db)
        self.repo = SqliteCharacterRepository(db)
        self.service = CharacterService(self.repo, self.engine)
        self.ctx = DiscordJdrContext(
            settings=DiscordSettings(use_engine_v2=True),
            rule_engine=self.engine,
            character_service=self.service,
        )
        self.owner_id = 4242
        self.guild_id = "555"
        self.clerc = self.service.create_from_wizard(
            owner_id=str(self.owner_id),
            guild_id=self.guild_id,
            name="ClercActif",
            **cleric_creation_kwargs(),
        )
        self.mage = self.service.create_from_wizard(
            owner_id=str(self.owner_id),
            guild_id=self.guild_id,
            name="MageSecond",
            **wizard_creation_kwargs(),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_roll_uses_active_character(self):
        self.service.set_active_character(
            str(self.owner_id), self.guild_id, self.mage.id
        )
        resolved = resolve_character_for_roll(
            self.ctx,
            self.owner_id,
            None,
            guild_id=self.guild_id,
        )
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.name, "MageSecond")

    def test_roll_without_active_on_multi_char(self):
        self.repo.clear_active_character(str(self.owner_id), self.guild_id)
        result = execute_roll(
            "d20",
            "normal",
            self.ctx,
            self.owner_id,
            guild_id=self.guild_id,
            rng=SequenceRng([10]),
        )
        self.assertFalse(result.traits_active)

    def test_sort_uses_active_cleric(self):
        self.service.set_active_character(
            str(self.owner_id), self.guild_id, self.clerc.id
        )
        display = execute_spell_cast(
            self.ctx,
            owner_id=self.owner_id,
            perso=None,
            spell_id="sacred_flame",
            guild_id=self.guild_id,
        )
        self.assertEqual(display.character_name, "ClercActif")

    def test_sort_unknown_without_active_raises(self):
        self.repo.clear_active_character(str(self.owner_id), self.guild_id)
        with self.assertRaises(DiceError):
            execute_spell_cast(
                self.ctx,
                owner_id=self.owner_id,
                perso=None,
                spell_id="sacred_flame",
                guild_id=self.guild_id,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
