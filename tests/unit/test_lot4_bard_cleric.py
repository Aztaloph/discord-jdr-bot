# tests/unit/test_lot4_bard_cleric.py
"""Lot 4 — Barde & Clerc SRD 2014 (lanceurs complets niv. 1–3)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import LevelUpPendingChoice, apply_level_up
from jdr_engine.rules.class_features.bard import (
    bardic_inspiration_remaining,
    bardic_inspiration_uses_max,
)
from jdr_engine.rules.class_features.cleric import (
    channel_divinity_remaining,
    preserve_life_remaining,
)
from jdr_engine.rules.spellcasting.access import has_spellcasting_access
from jdr_engine.rules.spellcasting.cast import cast_spell, get_spellcasting_stats
from jdr_engine.rules.spellcasting.preparation import cleric_prepared_capacity
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
from jdr_engine.rules.spellcasting.state import (
    get_cantrips_known,
    get_domain_spells,
    get_slots_used,
    get_spells_prepared_list,
)
from tests.helpers.creation import (
    bard_creation_kwargs,
    cleric_creation_kwargs,
    paladin_creation_kwargs,
)


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestLot4Bard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_bard_level_1_spellcasting_and_inspiration(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Melody",
            engine=self.engine,
            **bard_creation_kwargs(level=1),
        )
        self.assertTrue(has_spellcasting_access(char, self.engine))
        self.assertEqual(len(get_cantrips_known(char)), 2)
        mod, attack, dc = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod, 2)  # CHA 15
        self.assertEqual(dc, 12)
        self.assertEqual(get_max_spell_slots("bard", 1), {1: 2})
        max_insp = bardic_inspiration_uses_max(15)
        self.assertEqual(
            bardic_inspiration_remaining(char.choices or {}, cha_score=15),
            max_insp,
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Tours de magie", sheet.spellcasting_summary or "")

    def test_bard_level_up_to_3_lore(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Melody",
            engine=self.engine,
            **bard_creation_kwargs(level=1),
        )
        char, r2 = apply_level_up(char, self.engine)
        self.assertEqual(r2.new_level, 2)
        sheet2 = build_character_sheet(char, self.engine)
        self.assertTrue(any("Touche-à-tout" in line for line in sheet2.class_features_lines))
        self.assertTrue(any("Chant de repos" in line for line in sheet2.class_features_lines))

        with self.assertRaises(LevelUpPendingChoice):
            apply_level_up(char, self.engine)
        char, r3 = apply_level_up(
            char,
            self.engine,
            subclass="lore",
            expertise_skills=["performance", "persuasion"],
            lore_bonus_skills=["arcana", "history", "investigation"],
        )
        self.assertEqual(r3.new_level, 3)
        self.assertEqual(char.choices.get("specialization"), "lore")
        sheet3 = build_character_sheet(char, self.engine)
        self.assertTrue(any("Expertise" in line for line in sheet3.class_features_lines))
        self.assertTrue(any("Savoir" in line for line in sheet3.class_features_lines))

    def test_bard_cantrip_and_spell_cast(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Melody",
            engine=self.engine,
            **bard_creation_kwargs(level=1),
        )
        before_slots = dict(get_slots_used(char))
        cast_spell(char, "vicious_mockery", self.engine, rng=SequenceRng([12]))
        after_cantrip = dict(get_slots_used(char))
        self.assertEqual(before_slots, after_cantrip)

        result = cast_spell(
            char,
            "healing_word",
            self.engine,
            rng=SequenceRng([5]),
            persist_slots=True,
        )
        self.assertEqual(result.slot_consumed_level, 1)
        used = get_slots_used(result.updated_character)
        self.assertEqual(sum(used.values()), 1)


class TestLot4Cleric(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_cleric_level_1_domain_life(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Marie",
            engine=self.engine,
            **cleric_creation_kwargs(level=1),
        )
        self.assertEqual(char.choices.get("specialization"), "life")
        self.assertEqual(len(get_cantrips_known(char)), 3)
        capacity = cleric_prepared_capacity(2, 1)  # SAG 15 → mod +2
        prepared = get_spells_prepared_list(char)
        domain = get_domain_spells(char)
        self.assertEqual(len(prepared), capacity)
        self.assertIn("bless", domain)
        self.assertIn("cure_wounds", domain)
        self.assertNotIn("bless", prepared)
        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Armures lourdes", sheet.armor_proficiencies_text)
        self.assertIn("Domaine (gratuits)", sheet.spellcasting_summary or "")

    def test_cleric_level_up_to_3(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Marie",
            engine=self.engine,
            **cleric_creation_kwargs(level=1),
        )
        char, r2 = apply_level_up(char, self.engine)
        self.assertEqual(r2.new_level, 2)
        self.assertEqual(channel_divinity_remaining(char.choices or {}, level=2), 1)
        self.assertEqual(preserve_life_remaining(char.choices or {}, level=2), 10)
        sheet2 = build_character_sheet(char, self.engine)
        self.assertTrue(any("Canalisation" in line for line in sheet2.class_features_lines))
        self.assertTrue(any("Préservation" in line for line in sheet2.class_features_lines))

        char, r3 = apply_level_up(char, self.engine)
        self.assertEqual(r3.new_level, 3)
        self.assertEqual(get_max_spell_slots("cleric", 3), {1: 4, 2: 2})
        domain = get_domain_spells(char)
        self.assertIn("spiritual_weapon", domain)

    def test_cleric_cantrip_domain_spell_and_disciple_of_life(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Marie",
            engine=self.engine,
            **cleric_creation_kwargs(level=1),
        )
        char.hp_max = 30
        char.hp_current = 10
        cast_spell(char, "guidance", self.engine)  # cantrip utility

        result = cast_spell(
            char,
            "cure_wounds",
            self.engine,
            rng=SequenceRng([5]),
            persist_slots=True,
        )
        # 1d8=5 +2 SAG +3 Disciple (niv.1) = 10
        self.assertEqual(result.healing_total, 10)
        self.assertEqual(result.healing_applied, 10)


class TestLot4PaladinFightingStyleFr(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_great_weapon_fighting_display_fr(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=2, fighting_style="great_weapon_fighting"),
        )
        sheet = build_character_sheet(char, self.engine)
        style_lines = [
            line for line in sheet.class_features_lines if "Style de combat" in line
        ]
        self.assertEqual(len(style_lines), 1)
        self.assertIn("Style de combat —", style_lines[0])
        self.assertIn("Armes lourdes", style_lines[0])
        self.assertNotIn("Great Weapon", style_lines[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
