# tests/unit/test_spell_autocomplete.py
"""Autocomplétion /sort — sorts possédés par le personnage."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import CharacterService
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.state import list_castable_spell_ids, list_spell_autocomplete_ids

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.handlers.spell import (
    build_lot_b_spell_autocomplete_choices,
    build_sort_autocomplete_choices,
    build_spell_autocomplete_choices,
    list_available_spells,
)
from interfaces.discord.settings import DiscordSettings
from tests.helpers.creation import wizard_creation_kwargs


class TestSpellAutocomplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_all_ten_spells_when_empty_query(self):
        choices = build_lot_b_spell_autocomplete_choices(self.engine, "")
        self.assertEqual(len(choices), 25)

    def test_all_five_wizard_spells_when_empty_query(self):
        choices = build_spell_autocomplete_choices(self.engine, "", class_id="wizard")
        self.assertEqual(len(choices), 14)

    def test_partial_fire_matches_fire_bolt(self):
        choices = build_lot_b_spell_autocomplete_choices(self.engine, "fire")
        values = [c.value for c in choices]
        self.assertIn("fire_bolt", values)

    def test_partial_id_fire_bolt(self):
        choices = build_lot_b_spell_autocomplete_choices(self.engine, "fire_bolt")
        values = [c.value for c in choices]
        self.assertEqual(values, ["fire_bolt"])

    def test_french_label_trait(self):
        choices = build_lot_b_spell_autocomplete_choices(self.engine, "trait")
        values = [c.value for c in choices]
        self.assertIn("fire_bolt", values)

    def test_known_spell_ids_empty_returns_empty_without_error(self):
        choices = build_spell_autocomplete_choices(
            self.engine, "", known_spell_ids=[]
        )
        self.assertEqual(choices, [])

    def test_known_spell_ids_only_owned_spells(self):
        owned = ["fire_bolt", "burning_hands"]
        choices = build_spell_autocomplete_choices(
            self.engine, "", known_spell_ids=owned
        )
        values = [c.value for c in choices]
        self.assertEqual(set(values), set(owned))
        self.assertNotIn("scorching_ray", values)


class TestSortAutocompleteIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Path(self.tmp.name) / "bot.db"
        init_database(db)
        self.service = CharacterService(
            SqliteCharacterRepository(db), self.engine
        )
        self.ctx = DiscordJdrContext(
            settings=DiscordSettings(use_engine_v2=True),
            rule_engine=self.engine,
            character_service=self.service,
        )
        self.owner_id = 9001
        self.guild_id = "777"
        self.wizard = self.service.create_from_wizard(
            owner_id=str(self.owner_id),
            guild_id=self.guild_id,
            name="Merlin",
            **wizard_creation_kwargs(),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_wizard_lot1_shows_only_owned_spells(self):
        expected = list_spell_autocomplete_ids(self.wizard)
        self.assertEqual(
            expected,
            [
                "fire_bolt",
                "thaumaturgy",
                "guidance",
                "chromatic_orb",
                "burning_hands",
                "detect_magic",
                "magic_missile",
                "shield",
                "hellish_rebuke",
            ],
        )
        choices = build_sort_autocomplete_choices(
            self.ctx,
            owner_id=self.owner_id,
            perso=None,
            guild_id=self.guild_id,
            current="",
        )
        values = [c.value for c in choices]
        self.assertEqual(values, expected)
        prepared = set(self.wizard.choices["spellcasting"]["spells_prepared"])
        for choice in choices:
            if choice.value in prepared or choice.value in (
                self.wizard.choices["spellcasting"]["cantrips_known"]
            ):
                if choice.value in prepared and choice.value not in (
                    self.wizard.choices["spellcasting"]["cantrips_known"]
                ):
                    self.assertTrue(
                        choice.name.startswith("✨ ") or choice.name.startswith("📘 "),
                        choice.name,
                    )
                elif choice.value in self.wizard.choices["spellcasting"]["cantrips_known"]:
                    self.assertTrue(choice.name.startswith("✨ "), choice.name)
            else:
                self.assertTrue(choice.name.startswith("📘 "), choice.name)

    def test_autocomplete_matches_list_available_spells(self):
        character = self.service.resolve_for_game(
            str(self.owner_id), self.guild_id, None
        )
        owned = list_available_spells(character)
        choices = build_sort_autocomplete_choices(
            self.ctx,
            owner_id=self.owner_id,
            perso=None,
            guild_id=self.guild_id,
            current="",
        )
        self.assertEqual([c.value for c in choices], owned)

    def test_no_character_returns_empty_not_crash(self):
        choices = build_sort_autocomplete_choices(
            self.ctx,
            owner_id=99999,
            perso=None,
            guild_id=self.guild_id,
            current="",
        )
        self.assertEqual(choices, [])

    def test_no_guild_returns_empty_not_crash(self):
        choices = build_sort_autocomplete_choices(
            self.ctx,
            owner_id=self.owner_id,
            perso=None,
            guild_id=None,
            current="",
        )
        self.assertEqual(choices, [])

    def test_partial_filter_fire(self):
        choices = build_sort_autocomplete_choices(
            self.ctx,
            owner_id=self.owner_id,
            perso=None,
            guild_id=self.guild_id,
            current="fire",
        )
        values = [c.value for c in choices]
        self.assertEqual(values, ["fire_bolt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
