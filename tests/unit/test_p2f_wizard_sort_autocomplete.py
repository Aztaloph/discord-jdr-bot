# tests/unit/test_p2f_wizard_sort_autocomplete.py
"""P2f — autocomplete /sort strict magicien (cantrips + préparés uniquement)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import CharacterService
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.spellcasting.autocomplete_availability import (
    SpellAutocompleteAvailability,
    compute_spell_autocomplete_availability,
    list_autocomplete_spell_ids,
)
from jdr_engine.rules.spellcasting.state import (
    get_spellbook,
    get_spells_prepared_list,
    list_spell_autocomplete_ids,
)

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.handlers.spell import build_sort_autocomplete_choices
from interfaces.discord.settings import DiscordSettings
from tests.helpers.creation import cleric_creation_kwargs, wizard_creation_kwargs


def _wizard(level: int, spellcasting: dict) -> Character:
    return Character(
        owner_id="1",
        name="Gandalf",
        race_id="human",
        class_id="wizard",
        level=level,
        ability_scores=AbilityScores(
            scores=dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 15)
        ),
        choices={"spellcasting": spellcasting},
    )


class TestP2fWizardSortAutocomplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_wizard_autocomplete_only_prepared_and_cantrips(self):
        char = _wizard(
            3,
            {
                "cantrips_known": ["fire_bolt", "thaumaturgy", "guidance"],
                "spellbook": [
                    "magic_missile",
                    "shield",
                    "burning_hands",
                    "detect_magic",
                    "chromatic_orb",
                    "scorching_ray",
                ],
                "spells_prepared": ["magic_missile", "shield"],
                "slots_used": {},
            },
        )
        ids = list_autocomplete_spell_ids(char, engine=self.engine)
        self.assertEqual(
            ids,
            ["fire_bolt", "thaumaturgy", "guidance", "magic_missile", "shield"],
        )
        self.assertNotIn("burning_hands", ids)
        self.assertIn("burning_hands", get_spellbook(char))

    def test_wizard_spellbook_not_prepared_absent_from_list(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "burning_hands"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
        )
        ids = list_spell_autocomplete_ids(char)
        self.assertIn("fire_bolt", ids)
        self.assertIn("magic_missile", ids)
        self.assertNotIn("burning_hands", ids)

    def test_wizard_cantrips_always_castable_never_locked(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt", "thaumaturgy"],
                "spellbook": ["magic_missile"],
                "spells_prepared": [],
                "slots_used": {"1": 1},
            },
        )
        for cantrip in ("fire_bolt", "thaumaturgy"):
            self.assertIn(cantrip, list_autocomplete_spell_ids(char, engine=self.engine))
            state, reason = compute_spell_autocomplete_availability(
                char, cantrip, engine=self.engine
            )
            self.assertEqual(state, SpellAutocompleteAvailability.CASTABLE, cantrip)
            self.assertIsNone(reason)

    def test_wizard_prepared_shows_castable_or_locked(self):
        char = _wizard(
            3,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "scorching_ray"],
                "spells_prepared": ["magic_missile", "scorching_ray"],
                "slots_used": {"1": 4, "2": 2},
            },
        )
        mm_state, _ = compute_spell_autocomplete_availability(
            char, "magic_missile", engine=self.engine
        )
        self.assertEqual(mm_state, SpellAutocompleteAvailability.LEVEL_INSUFFICIENT)
        sr_state, _ = compute_spell_autocomplete_availability(
            char, "scorching_ray", engine=self.engine
        )
        self.assertEqual(sr_state, SpellAutocompleteAvailability.LEVEL_INSUFFICIENT)

    def test_cleric_autocomplete_unchanged(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Clerc",
            engine=self.engine,
            **cleric_creation_kwargs(level=1),
        )
        ids = list_autocomplete_spell_ids(char, engine=self.engine)
        self.assertIn("sacred_flame", ids)
        self.assertTrue(len(ids) >= 3)

    def test_build_sort_autocomplete_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            init_database(db)
            service = CharacterService(SqliteCharacterRepository(db), self.engine)
            ctx = DiscordJdrContext(
                settings=DiscordSettings(use_engine_v2=True),
                rule_engine=self.engine,
                character_service=service,
            )
            owner_id = 9001
            guild_id = "777"
            wizard = service.create_from_wizard(
                owner_id=str(owner_id),
                guild_id=guild_id,
                name="Merlin",
                **wizard_creation_kwargs(),
            )
            prepared = set(get_spells_prepared_list(wizard))
            cantrips = set(wizard.choices["spellcasting"]["cantrips_known"])
            choices = build_sort_autocomplete_choices(
                ctx,
                owner_id=owner_id,
                perso=None,
                guild_id=guild_id,
                current="",
            )
            values = {c.value for c in choices}
            for spell_id in values:
                self.assertIn(spell_id, cantrips | prepared)
            for spell_id in get_spellbook(wizard):
                if spell_id not in prepared and spell_id not in cantrips:
                    self.assertNotIn(spell_id, values)
            for choice in choices:
                if choice.value in cantrips:
                    self.assertTrue(choice.name.startswith("✨ "), choice.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
