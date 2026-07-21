# tests/unit/test_lot5_wizard_sorcerer.py
"""Lot 5 — Magicien (grimoire) & Ensorceleur SRD 2014 (niv. 1–3)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import LevelUpPendingChoice, apply_level_up
from jdr_engine.rules.class_features.sorcerer import (
    convert_slot_to_sorcery_points,
    convert_sorcery_points_to_slot,
    sorcery_points_max,
    sorcery_points_remaining,
)
from jdr_engine.rules.class_features.wizard import arcane_recovery_pool
from jdr_engine.rules.spellcasting.cast import SpellCastError, cast_spell
from jdr_engine.rules.spellcasting.preparation import wizard_prepared_capacity
from jdr_engine.rules.spellcasting.state import (
    get_cantrips_known,
    get_spellbook,
    get_spells_prepared_list,
)
from tests.helpers.creation import sorcerer_creation_kwargs, wizard_creation_kwargs


class TestLot5Wizard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_wizard_level_1_spellbook_and_preparation(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        self.assertEqual(len(get_cantrips_known(char)), 3)
        self.assertEqual(len(get_spellbook(char)), 6)
        capacity = wizard_prepared_capacity(2, 1)  # INT 15
        self.assertEqual(len(get_spells_prepared_list(char)), capacity)
        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Grimoire", sheet.spellcasting_summary or "")
        self.assertIn("Préparés", sheet.spellcasting_summary or "")
        self.assertTrue(
            any("Récupération arcanique" in line for line in sheet.class_features_lines)
        )

    def test_wizard_level_up_evocation(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        with self.assertRaises(LevelUpPendingChoice):
            apply_level_up(char, self.engine)
        char, r2 = apply_level_up(char, self.engine, subclass="evocation")
        self.assertEqual(r2.new_level, 2)
        self.assertEqual(char.choices.get("specialization"), "evocation")
        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Évocation", sheet.specialization_label or "")

    def test_wizard_level_3_spellbook_growth(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, subclass="evocation")
        char, r3 = apply_level_up(char, self.engine)
        self.assertEqual(r3.new_level, 3)
        self.assertEqual(len(get_cantrips_known(char)), 4)
        self.assertEqual(len(get_spellbook(char)), 8)
        self.assertEqual(arcane_recovery_pool(3), 2)

    def test_wizard_rejects_unprepared_spell(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        book = get_spellbook(char)
        prepared = set(get_spells_prepared_list(char))
        unprepared = next(s for s in book if s not in prepared)
        with self.assertRaises(SpellCastError) as ctx:
            cast_spell(char, unprepared, self.engine)
        self.assertIn("grimoire", str(ctx.exception).lower())


class TestLot5Sorcerer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_sorcerer_level_1_draconic(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Kael",
            engine=self.engine,
            **sorcerer_creation_kwargs(level=1),
        )
        self.assertEqual(char.choices.get("specialization"), "draconic")
        self.assertEqual(char.choices.get("sorcerer_dragon_type"), "red")
        self.assertEqual(len(get_cantrips_known(char)), 4)
        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Rouge", sheet.specialization_label or "")
        self.assertEqual(sheet.ac, 13 + 2)  # DEX 14
        self.assertGreater(sheet.hp_max, 8)  # +1 PV lignée

    def test_sorcerer_sorcery_points_level_2(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Kael",
            engine=self.engine,
            **sorcerer_creation_kwargs(level=1),
        )
        char, r2 = apply_level_up(char, self.engine)
        self.assertEqual(r2.new_level, 2)
        self.assertEqual(sorcery_points_max(2), 2)
        self.assertEqual(sorcery_points_remaining(char.choices or {}, level=2), 2)

    def test_sorcerer_point_slot_conversion(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Kael",
            engine=self.engine,
            **sorcerer_creation_kwargs(level=2),
        )
        from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
        from jdr_engine.rules.spellcasting.state import get_slots_used

        char.choices["spellcasting"]["slots_used"] = {"1": 2}
        used = get_slots_used(char)
        choices, used_after = convert_slot_to_sorcery_points(
            char.choices or {}, level=2, slot_level=1, slots_used=used
        )
        self.assertEqual(sorcery_points_remaining(choices, level=2), 2)
        max_slots = get_max_spell_slots("sorcerer", 2)
        choices, used2 = convert_sorcery_points_to_slot(
            choices, level=2, slot_level=1, slots_used=used_after, max_slots=max_slots
        )
        self.assertEqual(sorcery_points_remaining(choices, level=2), 0)

    def test_sorcerer_level_3_metamagic_pending(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Kael",
            engine=self.engine,
            **sorcerer_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        self.assertEqual(ctx.exception.pending.choice_type, "metamagic_options")
        char, r3 = apply_level_up(
            char, self.engine, metamagic_options=["quickened", "extended"]
        )
        self.assertEqual(r3.new_level, 3)
        self.assertEqual(len(get_cantrips_known(char)), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
