# tests/unit/test_p2h_wizard_grimoire_migration.py
"""P2h — migration batch grimoires mage (service + embeds)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jdr_engine.application.character_service import CharacterService
from jdr_engine.application.dto.wizard_grimoire_migration import (
    WizardGrimoireMigrationStatus,
)
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.spells_catalog import WIZARD_SPELLBOOK_POOL
from jdr_engine.rules.spellcasting.state import get_spellbook

from interfaces.discord.handlers.mj_grimoire_migration import (
    build_migration_preview_embed,
    format_migration_entry_line,
)

from tests.helpers.creation import cleric_creation_kwargs, wizard_creation_kwargs
from tests.unit.test_p2g_mj_grimoire_reset import _polluted_wizard_level1


class TestP2hWizardGrimoireMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def _service(self, db_path: Path) -> CharacterService:
        init_database(db_path)
        return CharacterService(SqliteCharacterRepository(db_path), self.engine)

    def _save_polluted(self, service: CharacterService, guild_id: str, name: str):
        char = service.create_from_wizard(
            owner_id="1",
            guild_id=guild_id,
            name=name,
            **wizard_creation_kwargs(),
        )
        char.choices = dict(char.choices or {})
        char.choices["spellcasting"] = _polluted_wizard_level1().choices["spellcasting"]
        service.save(char)
        return char

    def test_preview_empty_guild_no_wizards(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            report = service.migrate_wizard_grimoires_on_guild("555", dry_run=True)
            self.assertTrue(report.dry_run)
            self.assertEqual(report.total_wizards, 0)
            self.assertEqual(report.to_modify, 0)
            embed = build_migration_preview_embed(report)
            self.assertIn("Aucun magicien", embed.description or "")

    def test_preview_mixed_polluted_and_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            self._save_polluted(service, "555", "Pollu1")
            self._save_polluted(service, "555", "Pollu2")
            service.create_from_wizard(
                owner_id="2",
                guild_id="555",
                name="Propre",
                **wizard_creation_kwargs(),
            )
            service.create_from_wizard(
                owner_id="3",
                guild_id="555",
                name="Clerc",
                **cleric_creation_kwargs(),
            )
            report = service.migrate_wizard_grimoires_on_guild("555", dry_run=True)
            self.assertEqual(report.total_wizards, 3)
            self.assertEqual(report.to_modify, 2)
            self.assertEqual(report.skipped, 1)
            self.assertEqual(report.failed, 0)

    def test_preview_polluted_entry_has_will_modify_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            self._save_polluted(service, "555", "Joe")
            report = service.migrate_wizard_grimoires_on_guild("555", dry_run=True)
            entry = report.entries[0]
            self.assertEqual(entry.status, WizardGrimoireMigrationStatus.WILL_MODIFY)
            assert entry.result is not None
            self.assertIn("bless", entry.result.removed_from_spellbook)

    def test_preview_clean_entry_has_skip_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            service.create_from_wizard(
                owner_id="1",
                guild_id="555",
                name="Clean",
                **wizard_creation_kwargs(),
            )
            report = service.migrate_wizard_grimoires_on_guild("555", dry_run=True)
            entry = report.entries[0]
            self.assertEqual(entry.status, WizardGrimoireMigrationStatus.SKIP)
            assert entry.result is not None
            self.assertTrue(entry.result.already_clean)

    def test_apply_modifies_only_polluted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            polluted = self._save_polluted(service, "555", "Pollu")
            clean = service.create_from_wizard(
                owner_id="2",
                guild_id="555",
                name="Propre",
                **wizard_creation_kwargs(),
            )
            clean_book = list(get_spellbook(clean))

            report = service.migrate_wizard_grimoires_on_guild("555", dry_run=False)
            self.assertEqual(report.modified, 1)
            self.assertEqual(report.skipped, 1)

            reloaded_polluted = service.get_on_guild(polluted.id, "555")
            reloaded_clean = service.get_on_guild(clean.id, "555")
            self.assertEqual(get_spellbook(reloaded_polluted), list(WIZARD_SPELLBOOK_POOL[:6]))
            self.assertEqual(get_spellbook(reloaded_clean), clean_book)

    def test_apply_second_run_all_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            self._save_polluted(service, "555", "Joe")
            first = service.migrate_wizard_grimoires_on_guild("555", dry_run=False)
            self.assertEqual(first.modified, 1)
            second = service.migrate_wizard_grimoires_on_guild("555", dry_run=False)
            self.assertEqual(second.modified, 0)
            self.assertEqual(second.skipped, 1)

    def test_apply_continues_on_single_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            first = self._save_polluted(service, "555", "A")
            second = self._save_polluted(service, "555", "B")
            original_save = service._repo.save

            def flaky_save(character):
                if character.id == second.id:
                    raise RuntimeError("save simulé")
                return original_save(character)

            with patch.object(service._repo, "save", side_effect=flaky_save):
                report = service.migrate_wizard_grimoires_on_guild("555", dry_run=False)

            self.assertEqual(report.modified, 1)
            self.assertEqual(report.failed, 1)
            self.assertEqual(get_spellbook(service.get_on_guild(first.id, "555")), list(WIZARD_SPELLBOOK_POOL[:6]))
            self.assertIn("bless", get_spellbook(service.get_on_guild(second.id, "555")))

    def test_dry_run_never_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            char = self._save_polluted(service, "555", "Joe")
            before = list(get_spellbook(service.get_on_guild(char.id, "555")))
            service.migrate_wizard_grimoires_on_guild("555", dry_run=True)
            after = list(get_spellbook(service.get_on_guild(char.id, "555")))
            self.assertEqual(before, after)
            self.assertIn("bless", after)

    def test_confirm_embed_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            self._save_polluted(service, "555", "P1")
            self._save_polluted(service, "555", "P2")
            service.create_from_wizard(
                owner_id="2",
                guild_id="555",
                name="Clean",
                **wizard_creation_kwargs(),
            )
            report = service.migrate_wizard_grimoires_on_guild("555", dry_run=True)
            embed = build_migration_preview_embed(report)
            desc = embed.description or ""
            self.assertIn("Magiciens sur ce serveur : **3**", desc)
            self.assertIn("Seront modifiés : **2**", desc)
            self.assertIn("Déjà conformes (skip) : **1**", desc)
            modify_entry = next(
                e for e in report.entries if e.status == WizardGrimoireMigrationStatus.WILL_MODIFY
            )
            line = format_migration_entry_line(modify_entry)
            self.assertIn("grimoire : -bless", line)

    def test_apply_rescans_fresh_state_not_frozen_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            char = self._save_polluted(service, "555", "Joe")
            preview = service.migrate_wizard_grimoires_on_guild("555", dry_run=True)
            self.assertEqual(preview.to_modify, 1)

            service.reset_wizard_grimoire_on_guild(char.id, "555")

            apply_report = service.migrate_wizard_grimoires_on_guild("555", dry_run=False)
            self.assertEqual(apply_report.modified, 0)
            self.assertEqual(apply_report.skipped, 1)
            self.assertEqual(apply_report.failed, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
