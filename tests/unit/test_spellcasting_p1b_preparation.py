# tests/unit/test_spellcasting_p1b_preparation.py
"""Passe 2 / Lot P1b — builds druide (préparés) & occultiste (connus quota)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import apply_level_up
from jdr_engine.rules.spellcasting.cast import SpellCastError, cast_spell
from jdr_engine.rules.spellcasting.model import (
    druid_prepared_capacity,
    spells_known_capacity,
)
from jdr_engine.rules.spellcasting.preparation import (
    build_druid_spellcasting,
    build_warlock_spellcasting,
    upgrade_druid_spellcasting,
    upgrade_warlock_spellcasting,
)
from jdr_engine.rules.spellcasting.state import (
    get_spells_known,
    get_spells_prepared_list,
    spell_is_known,
)
from tests.helpers.creation import druid_creation_kwargs, warlock_creation_kwargs


class TestDruidPreparedBuild(unittest.TestCase):
    def test_build_druid_level_1_prepared_shape(self):
        sc = build_druid_spellcasting(1, wis_mod=2)
        self.assertIn("spells_prepared", sc)
        self.assertNotIn("spells_known", sc)
        self.assertEqual(len(sc["spells_prepared"]), druid_prepared_capacity(2, 1))
        self.assertEqual(
            sc["spells_prepared"],
            ["entangle", "cure_wounds", "faerie_fire"],
        )

    def test_build_druid_level_3_includes_flaming_sphere(self):
        sc = build_druid_spellcasting(3, wis_mod=2)
        capacity = druid_prepared_capacity(2, 3)
        self.assertEqual(len(sc["spells_prepared"]), min(capacity, 4))
        self.assertIn("flaming_sphere", sc["spells_prepared"])

    def test_upgrade_druid_merges_existing_prepared(self):
        choices = {
            "spellcasting": {
                "cantrips_known": ["druidcraft"],
                "spells_prepared": ["entangle"],
                "slots_used": {},
            }
        }
        updated = upgrade_druid_spellcasting(choices, new_level=3, wis_mod=2)
        prepared = updated["spellcasting"]["spells_prepared"]
        self.assertIn("entangle", prepared)
        self.assertIn("flaming_sphere", prepared)
        self.assertLessEqual(len(prepared), druid_prepared_capacity(2, 3))


class TestWarlockKnownBuild(unittest.TestCase):
    def test_build_warlock_level_1_quota(self):
        sc = build_warlock_spellcasting(1)
        self.assertEqual(len(sc["spells_known"]), spells_known_capacity("warlock", 1))
        self.assertEqual(sc["spells_known"], ["hex", "armor_of_agathys"])

    def test_build_warlock_level_2_includes_darkness(self):
        sc = build_warlock_spellcasting(2)
        self.assertEqual(len(sc["spells_known"]), 3)
        self.assertIn("darkness", sc["spells_known"])

    def test_upgrade_warlock_merges_existing_known(self):
        choices = {
            "spellcasting": {
                "cantrips_known": ["eldritch_blast"],
                "spells_known": ["hex"],
                "slots_used": {},
                "pact_magic": True,
            }
        }
        updated = upgrade_warlock_spellcasting(
            choices,
            new_level=2,
            old_level=1,
        )
        known = updated["spellcasting"]["spells_known"]
        self.assertIn("hex", known)
        self.assertIn("darkness", known)
        self.assertEqual(len(known), spells_known_capacity("warlock", 2))


class TestLegacyUnchangedWithP1a(unittest.TestCase):
    def test_legacy_druid_spells_known_still_castable(self):
        char = Character(
            owner_id="1",
            name="Legacy Druid",
            race_id="human",
            class_id="druid",
            level=1,
            ability_scores=AbilityScores(
                scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 15, "cha": 10}
            ),
            choices={
                "spellcasting": {
                    "cantrips_known": ["druidcraft"],
                    "spells_known": ["entangle", "cure_wounds", "faerie_fire"],
                    "slots_used": {},
                }
            },
        )
        self.assertTrue(spell_is_known(char, "cure_wounds"))
        self.assertEqual(get_spells_known(char), ["entangle", "cure_wounds", "faerie_fire"])


class TestFinalizeDruidWarlockP1b(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_finalize_druid_level_3_progression(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Rowan",
            engine=self.engine,
            **druid_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(
            char,
            self.engine,
            subclass="land",
            subchoice_value="forest",
        )
        char, _ = apply_level_up(char, self.engine, subclass="land")
        prepared = get_spells_prepared_list(char)
        self.assertIn("flaming_sphere", prepared)
        self.assertNotIn("spells_known", char.choices.get("spellcasting") or {})

    def test_finalize_warlock_level_3_casts_darkness(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=3),
        )
        self.assertIn("darkness", get_spells_known(char))
        result = cast_spell(char, "darkness", self.engine, persist_slots=False)
        self.assertEqual(result.spell_id, "darkness")

    def test_finalize_warlock_level_2_darkness_known_not_castable(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=2),
        )
        self.assertTrue(spell_is_known(char, "darkness"))
        with self.assertRaises(SpellCastError):
            cast_spell(char, "darkness", self.engine, persist_slots=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
