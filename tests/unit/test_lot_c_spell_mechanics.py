# tests/unit/test_lot_c_spell_mechanics.py
"""Passe 1 / Lot C — métadonnées mécaniques des sorts niveau 2 SRD 2014."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.compendium.loader import load_ruleset
from jdr_engine.compendium.schemas.spell import SpellMechanics
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.mechanics_display import (
    format_slot_scaling_summary,
)

LEVEL_2_SPELL_IDS: frozenset[str] = frozenset(
    {
        "darkness",
        "flaming_sphere",
        "scorching_ray",
        "spiritual_weapon",
    }
)

OFFENSIVE_LEVEL_2: frozenset[str] = frozenset(
    {
        "flaming_sphere",
        "scorching_ray",
        "spiritual_weapon",
    }
)

SLOT_SCALING_UPCAST: dict[str, dict] = {
    "scorching_ray": {"missiles": 1},
    "flaming_sphere": {"damage_dice": "1d6"},
    "spiritual_weapon": {"damage_dice": "1d8"},
}

NO_SLOT_SCALING: frozenset[str] = frozenset({"darkness"})

CONCENTRATION_SPELLS: frozenset[str] = frozenset(
    {
        "darkness",
        "flaming_sphere",
    }
)


class TestLotCSpellMechanics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)
        _, _, entries = load_ruleset("dnd5e")
        cls.spell_entries = {
            entry.entry_id: entry.definition.mechanics
            for entry in entries
            if entry.definition.type == "spell"
        }

    def test_all_compendium_level_2_spells_listed(self):
        level_2 = {
            sid
            for sid, mech in self.spell_entries.items()
            if int(mech.get("level", -1)) == 2
        }
        self.assertEqual(level_2, LEVEL_2_SPELL_IDS)

    def test_each_level_2_validates_spell_mechanics_schema(self):
        for spell_id in LEVEL_2_SPELL_IDS:
            with self.subTest(spell_id=spell_id):
                SpellMechanics.model_validate(self.spell_entries[spell_id])

    def test_offensive_level_2_have_damage_fields(self):
        for spell_id in OFFENSIVE_LEVEL_2:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                self.assertTrue(mech.get("damage_dice"))
                self.assertTrue(mech.get("damage_type"))

    def test_level_2_never_use_cantrip_scaling(self):
        for spell_id in LEVEL_2_SPELL_IDS:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                self.assertNotIn("cantrip_scaling", mech)

    def test_slot_scaling_upcast_spells(self):
        for spell_id, expected in SLOT_SCALING_UPCAST.items():
            with self.subTest(spell_id=spell_id):
                scaling = self.spell_entries[spell_id]["slot_scaling"]
                increment = scaling["per_slot_above_base"]
                for key, value in expected.items():
                    self.assertEqual(increment.get(key), value)

    def test_slot_scaling_null_on_non_upcast_spells(self):
        for spell_id in NO_SLOT_SCALING:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                self.assertIsNone(mech.get("slot_scaling"))

    def test_all_level_2_have_description(self):
        for spell_id in LEVEL_2_SPELL_IDS:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                desc = mech.get("description")
                self.assertIsInstance(desc, dict)
                self.assertTrue(desc.get("fr"))
                self.assertTrue(desc.get("en"))

    def test_concentration_flags(self):
        for spell_id in LEVEL_2_SPELL_IDS:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                expected = spell_id in CONCENTRATION_SPELLS
                self.assertEqual(bool(mech.get("concentration")), expected)

    def test_darkness_no_tiefling_note_in_effect(self):
        mech = self.spell_entries["darkness"]
        effect = mech.get("effect") or {}
        self.assertEqual(effect.get("type"), "utility")
        self.assertNotIn("srd_note", effect)
        racial = mech.get("racial_reference") or {}
        self.assertIn("tiefling", racial)
        self.assertIn("fr", racial["tiefling"])

    def test_darkness_material_component(self):
        components = self.spell_entries["darkness"]["components"]
        self.assertTrue(components.get("material"))
        mat = components.get("material_description") or {}
        self.assertTrue(mat.get("fr"))
        self.assertTrue(mat.get("en"))

    def test_scorching_ray_slot_scaling_display_uses_rayons(self):
        line = format_slot_scaling_summary(
            self.spell_entries["scorching_ray"],
            spell_id="scorching_ray",
        )
        self.assertIsNotNone(line)
        self.assertIn("rayon", line)
        self.assertNotIn("dard", line)

    def test_magic_missile_slot_scaling_display_uses_dards(self):
        line = format_slot_scaling_summary(
            self.spell_entries["magic_missile"],
            spell_id="magic_missile",
        )
        self.assertIsNotNone(line)
        self.assertIn("dard", line)

    def test_all_28_spells_still_load_strict(self):
        self.assertEqual(len(self.spell_entries), 28)


if __name__ == "__main__":
    unittest.main(verbosity=2)
