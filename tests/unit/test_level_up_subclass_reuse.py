# tests/unit/test_level_up_subclass_reuse.py
"""Montée de niveau — ne pas re-exiger un sous-choix déjà enregistré."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import CharacterService
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_progression import LevelUpPendingChoice, apply_level_up
from tests.helpers.creation import (
    druid_creation_kwargs,
    sorcerer_creation_kwargs,
    warlock_creation_kwargs,
    wizard_creation_kwargs,
)


class TestLevelUpSubclassReuse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Path(self.tmp.name) / "bot.db"
        init_database(db)
        self.service = CharacterService(SqliteCharacterRepository(db), self.engine)
        self.guild_id = "900"

    def tearDown(self):
        self.tmp.cleanup()

    def test_sorcerer_level_3_metamagic_keeps_dragon_type(self):
        char = self.service.create_from_wizard(
            owner_id="1",
            guild_id=self.guild_id,
            name="Kael",
            **sorcerer_creation_kwargs(level=1),
        )
        self.assertEqual(char.choices.get("sorcerer_dragon_type"), "red")
        self.service.level_up_on_guild(char.id, self.guild_id)
        reloaded = self.service.get_on_guild(char.id, self.guild_id)
        with self.assertRaises(LevelUpPendingChoice):
            self.service.level_up_on_guild(reloaded.id, self.guild_id)
        result = self.service.complete_level_up_choice_on_guild(
            reloaded.id,
            self.guild_id,
            subclass="draconic",
            metamagic_options=["extended", "subtle"],
            base_character=reloaded,
        )
        final = self.service.get_on_guild(char.id, self.guild_id)
        self.assertEqual(result.new_level, 3)
        self.assertEqual(final.choices.get("specialization"), "draconic")
        self.assertEqual(final.choices.get("sorcerer_dragon_type"), "red")
        self.assertEqual(final.choices.get("metamagic_options"), ["extended", "subtle"])
        sheet = build_character_sheet(final, self.engine)
        self.assertIn("Rouge", sheet.specialization_label or "")

    def test_sorcerer_apply_level_up_with_existing_subclass_kwarg(self):
        char = self.service.create_from_wizard(
            owner_id="1",
            guild_id=self.guild_id,
            name="Kael",
            **sorcerer_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(
            self.service.get_on_guild(char.id, self.guild_id), self.engine
        )
        updated, result = apply_level_up(
            char,
            self.engine,
            subclass="draconic",
            metamagic_options=["quickened", "subtle"],
        )
        self.assertEqual(result.new_level, 3)
        self.assertEqual(updated.choices.get("sorcerer_dragon_type"), "red")

    def test_wizard_level_3_does_not_reask_evocation(self):
        char = self.service.create_from_wizard(
            owner_id="1",
            guild_id=self.guild_id,
            name="Merlin",
            **wizard_creation_kwargs(level=1),
        )
        self.service.level_up_on_guild(char.id, self.guild_id, subclass="evocation")
        reloaded = self.service.get_on_guild(char.id, self.guild_id)
        updated, result = apply_level_up(
            reloaded,
            self.engine,
            subclass="evocation",
        )
        self.assertEqual(result.new_level, 3)
        self.assertEqual(updated.choices.get("specialization"), "evocation")

    def test_druid_level_3_keeps_land_terrain(self):
        char = self.service.create_from_wizard(
            owner_id="1",
            guild_id=self.guild_id,
            name="Rowan",
            **druid_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(
            self.service.get_on_guild(char.id, self.guild_id),
            self.engine,
            subclass="land",
            subchoice_value="forest",
        )
        updated, result = apply_level_up(
            char,
            self.engine,
            subclass="land",
        )
        self.assertEqual(result.new_level, 3)
        self.assertEqual(updated.choices.get("druid_land_terrain"), "forest")
        sheet = build_character_sheet(updated, self.engine)
        self.assertIn("Forêt", sheet.specialization_label or "")

    def test_warlock_level_3_keeps_invocations(self):
        char = self.service.create_from_wizard(
            owner_id="1",
            guild_id=self.guild_id,
            name="Morrigan",
            **warlock_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(
            self.service.get_on_guild(char.id, self.guild_id),
            self.engine,
            eldritch_invocations=["agonizing_blast", "devils_sight"],
        )
        updated, result = apply_level_up(
            char,
            self.engine,
            eldritch_invocations=["agonizing_blast", "devils_sight"],
            pact_boon="pact_of_the_blade",
        )
        self.assertEqual(result.new_level, 3)
        self.assertEqual(
            updated.choices.get("eldritch_invocations"),
            ["agonizing_blast", "devils_sight"],
        )
        self.assertEqual(updated.choices.get("pact_boon"), "pact_of_the_blade")


if __name__ == "__main__":
    unittest.main(verbosity=2)
