# tests/unit/test_spell_autocomplete_availability.py
"""Autocomplete /sort — états ✨ / 🔒 / 📘 et priorité niveau > préparation."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import apply_level_up
from jdr_engine.rules.spellcasting.autocomplete_availability import (
    DISCORD_AUTOCOMPLETE_NAME_MAX,
    SpellAutocompleteAvailability,
    compute_spell_autocomplete_availability,
    format_autocomplete_choice_name,
    list_autocomplete_spell_ids,
)
from tests.helpers.creation import (
    paladin_creation_kwargs,
    ranger_creation_kwargs,
    warlock_creation_kwargs,
    wizard_creation_kwargs,
)


def _char(class_id: str, level: int, spellcasting: dict) -> Character:
    return Character(
        owner_id="1",
        name="Test",
        race_id="human",
        class_id=class_id,
        level=level,
        ability_scores=AbilityScores(
            scores=dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
        ),
        choices={"spellcasting": spellcasting},
    )


class TestAvailabilityPriority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_half_caster_level_1_all_locked(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Aragorn",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        for spell_id in ("hunters_mark", "cure_wounds", "detect_magic"):
            state, reason = compute_spell_autocomplete_availability(
                char, spell_id, engine=self.engine
            )
            self.assertEqual(state, SpellAutocompleteAvailability.LEVEL_INSUFFICIENT)
            self.assertEqual(reason, "niv. 2 requis")

    def test_paladin_level_1_lists_all_spells(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=1),
        )
        ids = list_autocomplete_spell_ids(char, engine=self.engine)
        self.assertEqual(
            ids,
            ["bless", "cure_wounds", "detect_magic"],
        )

    def test_ranger_level_2_prepared_castable_unprepared_not(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Aragorn",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, fighting_style="archery")
        char.choices["spellcasting"]["spells_prepared"] = [
            "hunters_mark",
            "cure_wounds",
        ]

        hm_state, _ = compute_spell_autocomplete_availability(
            char, "hunters_mark", engine=self.engine
        )
        self.assertEqual(hm_state, SpellAutocompleteAvailability.CASTABLE)

        dm_state, _ = compute_spell_autocomplete_availability(
            char, "detect_magic", engine=self.engine
        )
        self.assertEqual(dm_state, SpellAutocompleteAvailability.NOT_PREPARED)

    def test_warlock_level_2_darkness_level_before_preparation(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=2),
        )
        state, reason = compute_spell_autocomplete_availability(
            char, "darkness", engine=self.engine
        )
        self.assertEqual(state, SpellAutocompleteAvailability.LEVEL_INSUFFICIENT)
        self.assertEqual(reason, "niv. 2 requis")
        self.assertNotEqual(state, SpellAutocompleteAvailability.NOT_PREPARED)

    def test_wizard_unprepared_with_slots_is_not_prepared(self):
        char = _char(
            "wizard",
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "burning_hands"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
        )
        state, _ = compute_spell_autocomplete_availability(
            char, "burning_hands", engine=self.engine
        )
        self.assertEqual(state, SpellAutocompleteAvailability.NOT_PREPARED)

    def test_wizard_prepared_is_castable(self):
        char = _char(
            "wizard",
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
        )
        state, _ = compute_spell_autocomplete_availability(
            char, "magic_missile", engine=self.engine
        )
        self.assertEqual(state, SpellAutocompleteAvailability.CASTABLE)

    def test_cantrip_always_castable(self):
        char = _char(
            "wizard",
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": [],
                "spells_prepared": [],
                "slots_used": {},
            },
        )
        state, _ = compute_spell_autocomplete_availability(
            char, "fire_bolt", engine=self.engine
        )
        self.assertEqual(state, SpellAutocompleteAvailability.CASTABLE)

    def test_wizard_level_3_exhausted_slots_shows_depleted_not_level_required(self):
        char = _char(
            "wizard",
            3,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "chromatic_orb"],
                "spells_prepared": ["magic_missile", "chromatic_orb"],
                # niv. 3 magicien : 4 empl. niv. 1 + 2 empl. niv. 2 — tout consommé
                "slots_used": {"1": 4, "2": 2},
            },
        )
        state, reason = compute_spell_autocomplete_availability(
            char, "magic_missile", engine=self.engine
        )
        self.assertEqual(state, SpellAutocompleteAvailability.LEVEL_INSUFFICIENT)
        self.assertEqual(reason, "emplacements niv. 1 épuisés")
        self.assertNotIn("niv. 1 requis", reason)

        label = format_autocomplete_choice_name(
            "Projectile magique",
            "magic_missile",
            state,
            level_reason=reason,
        )
        self.assertIn("emplacements niv. 1 épuisés", label)
        self.assertTrue(label.startswith("🔒 "))

    def test_wizard_level_1_spell_level_2_still_shows_level_required(self):
        char = _char(
            "wizard",
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["scorching_ray"],
                "spells_prepared": ["scorching_ray"],
                "slots_used": {},
            },
        )
        state, reason = compute_spell_autocomplete_availability(
            char, "scorching_ray", engine=self.engine
        )
        self.assertEqual(state, SpellAutocompleteAvailability.LEVEL_INSUFFICIENT)
        self.assertEqual(reason, "niv. 2 requis")


class TestFormatAutocompleteChoiceName(unittest.TestCase):
    def test_castable_label(self):
        name = format_autocomplete_choice_name(
            "Soins",
            "cure_wounds",
            SpellAutocompleteAvailability.CASTABLE,
        )
        self.assertEqual(name, "✨ Soins (cure_wounds)")

    def test_locked_label(self):
        name = format_autocomplete_choice_name(
            "Bénédiction",
            "bless",
            SpellAutocompleteAvailability.LEVEL_INSUFFICIENT,
            level_reason="niv. 2 requis",
        )
        self.assertEqual(name, "🔒 Bénédiction (bless) — niv. 2 requis")

    def test_not_prepared_label(self):
        name = format_autocomplete_choice_name(
            "Détection de la magie",
            "detect_magic",
            SpellAutocompleteAvailability.NOT_PREPARED,
        )
        self.assertIn("📘", name)
        self.assertIn("non préparé", name)

    def test_truncation_under_100_chars(self):
        long_name = "A" * 80
        name = format_autocomplete_choice_name(
            long_name,
            "detect_magic",
            SpellAutocompleteAvailability.LEVEL_INSUFFICIENT,
            level_reason="niv. 2 requis",
        )
        self.assertLessEqual(len(name), DISCORD_AUTOCOMPLETE_NAME_MAX)
        self.assertIn("(detect_magic)", name)


class TestSortHandlerEnrichedLabels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_ranger_level_1_handler_choices(self):
        from interfaces.discord.handlers.spell import build_spell_autocomplete_choices

        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Aragorn",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        choices = build_spell_autocomplete_choices(
            self.engine, "", character=char
        )
        self.assertEqual(len(choices), 3)
        for choice in choices:
            self.assertTrue(choice.name.startswith("🔒 "))
            self.assertEqual(choice.value, choice.name.split("(")[1].split(")")[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
