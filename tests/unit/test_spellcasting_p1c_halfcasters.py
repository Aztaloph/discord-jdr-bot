# tests/unit/test_spellcasting_p1c_halfcasters.py
"""Passe 2 / Lot P1c — demi-lanceurs rôdeur & paladin (spells_prepared + slots SRD)."""
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
    PREPARED_CLASSES,
    paladin_prepared_capacity,
    ranger_prepared_capacity,
)
from jdr_engine.rules.spellcasting.preparation import (
    build_paladin_spellcasting,
    build_ranger_spellcasting,
)
from jdr_engine.rules.spellcasting.slots import (
    get_half_caster_max_spell_slots,
    get_max_spell_slots,
    half_caster_effective_full_level,
)
from jdr_engine.rules.spellcasting.state import (
    get_spells_known,
    get_spells_prepared_list,
    list_castable_spell_ids,
    spell_is_known,
)
from tests.helpers.creation import paladin_creation_kwargs, ranger_creation_kwargs


class TestHalfCasterSlotProgression(unittest.TestCase):
    def test_effective_full_caster_level(self):
        self.assertIsNone(half_caster_effective_full_level(1))
        self.assertEqual(half_caster_effective_full_level(2), 1)
        self.assertEqual(half_caster_effective_full_level(3), 2)
        self.assertEqual(half_caster_effective_full_level(5), 3)

    def test_ranger_slots_by_level(self):
        self.assertEqual(get_half_caster_max_spell_slots(1), {})
        self.assertEqual(get_half_caster_max_spell_slots(2), {1: 2})
        self.assertEqual(get_half_caster_max_spell_slots(3), {1: 3})
        self.assertEqual(get_half_caster_max_spell_slots(5), {1: 4, 2: 2})
        self.assertEqual(get_max_spell_slots("ranger", 2), {1: 2})
        self.assertEqual(get_max_spell_slots("paladin", 3), {1: 3})

    def test_paladin_slots_match_ranger(self):
        for level in (1, 2, 3, 5):
            self.assertEqual(
                get_half_caster_max_spell_slots(level),
                get_max_spell_slots("paladin", level)
                if level <= 3
                else get_half_caster_max_spell_slots(level),
            )


class TestRangerPreparedBuild(unittest.TestCase):
    def test_ranger_in_prepared_family(self):
        self.assertIn("ranger", PREPARED_CLASSES)

    def test_level_1_full_pool_visibility(self):
        sc = build_ranger_spellcasting(1, wis_mod=2)
        self.assertIn("spells_prepared", sc)
        self.assertNotIn("spells_known", sc)
        self.assertEqual(
            sc["spells_prepared"],
            ["hunters_mark", "cure_wounds", "detect_magic"],
        )

    def test_level_2_prepared_quota(self):
        sc = build_ranger_spellcasting(2, wis_mod=2)
        self.assertEqual(len(sc["spells_prepared"]), ranger_prepared_capacity(2))
        self.assertEqual(sc["spells_prepared"], ["hunters_mark", "cure_wounds"])


class TestPaladinPreparedBuild(unittest.TestCase):
    def test_level_1_full_pool_visibility(self):
        sc = build_paladin_spellcasting(1, cha_mod=2)
        self.assertEqual(
            sc["spells_prepared"],
            ["bless", "cure_wounds", "detect_magic"],
        )

    def test_level_2_prepared_capacity(self):
        sc = build_paladin_spellcasting(2, cha_mod=2)
        capacity = paladin_prepared_capacity(2, 2)
        self.assertEqual(len(sc["spells_prepared"]), capacity)
        self.assertIn("bless", sc["spells_prepared"])
        self.assertIn("detect_magic", sc["spells_prepared"])


class TestLegacyHalfCasters(unittest.TestCase):
    def test_ranger_legacy_spells_known_and_prepared(self):
        char = Character(
            owner_id="1",
            name="Legacy Ranger",
            race_id="human",
            class_id="ranger",
            level=2,
            ability_scores=AbilityScores(scores=dict.fromkeys(
                ("str", "dex", "con", "int", "wis", "cha"), 10
            ) | {"wis": 15}),
            choices={
                "spellcasting": {
                    "spells_known": ["hunters_mark", "cure_wounds"],
                    "spells_prepared": ["hunters_mark", "cure_wounds"],
                    "slots_used": {},
                }
            },
        )
        self.assertEqual(get_spells_known(char), ["hunters_mark", "cure_wounds"])
        self.assertTrue(spell_is_known(char, "hunters_mark"))

    def test_paladin_legacy_duplicate_keys(self):
        spells = ["bless", "cure_wounds"]
        char = Character(
            owner_id="1",
            name="Legacy Paladin",
            race_id="human",
            class_id="paladin",
            level=2,
            ability_scores=AbilityScores(scores=dict.fromkeys(
                ("str", "dex", "con", "int", "wis", "cha"), 10
            ) | {"cha": 14}),
            choices={
                "spellcasting": {
                    "spells_known": spells,
                    "spells_prepared": spells,
                    "slots_used": {},
                }
            },
        )
        self.assertEqual(get_spells_prepared_list(char), spells)


class TestFinalizeHalfCasters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_ranger_level_1_visible_no_slots(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Aragorn",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        self.assertIn("spellcasting", char.choices)
        self.assertEqual(get_max_spell_slots("ranger", 1), {})
        castable = list_castable_spell_ids(char)
        self.assertIn("hunters_mark", castable)
        with self.assertRaises(SpellCastError) as ctx:
            cast_spell(char, "hunters_mark", self.engine, persist_slots=False)
        self.assertIn("emplacement", str(ctx.exception).lower())

    def test_ranger_level_2_cast_hunters_mark(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Aragorn",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, fighting_style="archery")
        self.assertEqual(len(get_spells_prepared_list(char)), 2)
        result = cast_spell(char, "hunters_mark", self.engine, persist_slots=True)
        self.assertEqual(result.slot_consumed_level, 1)

    def test_paladin_level_1_visible_no_slots(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=1),
        )
        self.assertIn("bless", list_castable_spell_ids(char))
        with self.assertRaises(SpellCastError):
            cast_spell(char, "bless", self.engine, persist_slots=False)

    def test_paladin_level_2_three_prepared(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, fighting_style="defense")
        prepared = get_spells_prepared_list(char)
        self.assertEqual(len(prepared), paladin_prepared_capacity(2, 2))
        self.assertIn("detect_magic", prepared)


if __name__ == "__main__":
    unittest.main(verbosity=2)
