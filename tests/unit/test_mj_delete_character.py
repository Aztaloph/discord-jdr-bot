# tests/unit/test_mj_delete_character.py
"""Suppression de personnage par le MJ — /perso-supprimer."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from jdr_engine.application.character_service import CharacterNotFoundError, CharacterService
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine

from tests.helpers.creation import cleric_creation_kwargs, wizard_creation_kwargs

from interfaces.discord.permissions.mj import MJ_ROLE_NAME, user_has_mj_role


class TestMjDeleteCharacter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def _service(self, db_path: Path) -> CharacterService:
        init_database(db_path)
        return CharacterService(SqliteCharacterRepository(db_path), self.engine)

    def test_mj_can_delete_character_by_id_on_guild(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            created = service.create_from_wizard(
                owner_id="777",
                guild_id="555",
                name="Cible",
                **wizard_creation_kwargs(),
            )
            self.assertIsNotNone(service.get_on_guild(created.id, "555"))
            service.delete_on_guild(created.id, "555")
            with self.assertRaises(CharacterNotFoundError):
                service.get_on_guild(created.id, "555")

    def test_unknown_character_id_on_guild(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            with self.assertRaises(CharacterNotFoundError):
                service.get_on_guild("inconnu01", "555")

    def test_character_on_other_guild_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            created = service.create_from_wizard(
                owner_id="777",
                guild_id="555",
                name="Cible",
                **wizard_creation_kwargs(),
            )
            with self.assertRaises(CharacterNotFoundError):
                service.get_on_guild(created.id, "999")

    def test_list_by_guild_for_autocomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            service.create_from_wizard(
                owner_id="1",
                guild_id="555",
                name="Alice",
                **wizard_creation_kwargs(),
            )
            service.create_from_wizard(
                owner_id="2",
                guild_id="555",
                name="Bob",
                **cleric_creation_kwargs(),
            )
            service.create_from_wizard(
                owner_id="3",
                guild_id="999",
                name="Charlie",
                **wizard_creation_kwargs(),
            )
            on_guild = service.list_by_guild("555")
            self.assertEqual(len(on_guild), 2)
            names = {c.name for c in on_guild}
            self.assertEqual(names, {"Alice", "Bob"})

    def test_non_mj_role_denied(self):
        member = MagicMock()
        role = MagicMock()
        role.name = "Joueur"
        member.roles = [role]
        self.assertFalse(user_has_mj_role(member))

    def test_mj_role_allowed(self):
        member = MagicMock()
        role = MagicMock()
        role.name = MJ_ROLE_NAME
        member.roles = [role]
        self.assertTrue(user_has_mj_role(member))


class TestMjDeleteHandler(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    async def test_handler_refuses_non_mj(self):
        from interfaces.discord.handlers.mj_delete import mj_perso_supprimer

        interaction = MagicMock()
        interaction.guild = MagicMock()
        interaction.guild.id = 555
        interaction.response = MagicMock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.user = MagicMock()

        ctx = MagicMock()

        with patch(
            "interfaces.discord.handlers.mj_delete.require_mj_role",
            new=AsyncMock(return_value=False),
        ):
            await mj_perso_supprimer(interaction, ctx, "abc12345")

        interaction.response.send_message.assert_not_called()

    async def test_handler_unknown_character_id(self):
        from interfaces.discord.handlers.mj_delete import mj_perso_supprimer

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            init_database(db)
            service = CharacterService(SqliteCharacterRepository(db), self.engine)

            interaction = MagicMock()
            interaction.guild = MagicMock()
            interaction.guild.id = 555
            interaction.user = MagicMock()
            interaction.user.id = 1
            interaction.response = MagicMock()
            interaction.response.is_done.return_value = False
            interaction.response.send_message = AsyncMock()

            ctx = MagicMock()
            ctx.character_service = service

            with patch(
                "interfaces.discord.handlers.mj_delete.require_mj_role",
                new=AsyncMock(return_value=True),
            ):
                await mj_perso_supprimer(interaction, ctx, "inconnu01")

            interaction.response.send_message.assert_called_once()
            embed = interaction.response.send_message.call_args.kwargs["embed"]
            self.assertIn("introuvable", embed.title.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
