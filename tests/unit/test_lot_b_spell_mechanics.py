# tests/unit/test_lot_b_spell_mechanics.py
"""Passe 1 / Lot B — métadonnées mécaniques des sorts niveau 1 SRD 2014."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.compendium.loader import load_ruleset
from jdr_engine.compendium.schemas.spell import SpellMechanics
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.mechanics_display import (
    format_slot_scaling_summary,
)

LEVEL_1_SPELL_IDS: frozenset[str] = frozenset(
    {
        "armor_of_agathys",
        "bless",
        "burning_hands",
        "chromatic_orb",
        "cure_wounds",
        "detect_magic",
        "entangle",
        "faerie_fire",
        "healing_word",
        "hellish_rebuke",
        "hex",
        "hunters_mark",
        "inflict_wounds",
        "magic_missile",
        "shield",
    }
)

OFFENSIVE_LEVEL_1: frozenset[str] = frozenset(
    {
        "burning_hands",
        "chromatic_orb",
        "hellish_rebuke",
        "inflict_wounds",
        "magic_missile",
    }
)

SLOT_SCALING_UPCAST: dict[str, dict] = {
    "magic_missile": {"missiles": 1},
    "burning_hands": {"damage_dice": "1d6"},
    "hellish_rebuke": {"damage_dice": "1d10"},
    "inflict_wounds": {"damage_dice": "1d10"},
    "chromatic_orb": {"damage_dice": "1d8"},
    "cure_wounds": {"healing_dice": "1d8"},
    "healing_word": {"healing_dice": "1d4"},
    "bless": {"extra_targets": 1},
    "armor_of_agathys": {"temp_hp": 5, "cold_damage": 5},
}

NO_SLOT_SCALING: frozenset[str] = frozenset(
    {
        "shield",
        "detect_magic",
        "entangle",
        "faerie_fire",
        "hex",
        "hunters_mark",
    }
)


class TestLotBSpellMechanics(unittest.TestCase):
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

    def test_all_compendium_level_1_spells_listed(self):
        level_1 = {
            sid
            for sid, mech in self.spell_entries.items()
            if int(mech.get("level", -1)) == 1
        }
        self.assertEqual(level_1, LEVEL_1_SPELL_IDS)

    def test_each_level_1_validates_spell_mechanics_schema(self):
        for spell_id in LEVEL_1_SPELL_IDS:
            with self.subTest(spell_id=spell_id):
                SpellMechanics.model_validate(self.spell_entries[spell_id])

    def test_offensive_level_1_have_damage_fields(self):
        for spell_id in OFFENSIVE_LEVEL_1:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                self.assertTrue(mech.get("damage_dice"))
                self.assertTrue(mech.get("damage_type"))

    def test_level_1_never_use_cantrip_scaling(self):
        for spell_id in LEVEL_1_SPELL_IDS:
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

    def test_all_level_1_have_description(self):
        for spell_id in LEVEL_1_SPELL_IDS:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                desc = mech.get("description")
                self.assertIsInstance(desc, dict)
                self.assertTrue(desc.get("fr"))
                self.assertTrue(desc.get("en"))

    def test_cantrips_unchanged_lot_a_fields(self):
        for spell_id, mech in self.spell_entries.items():
            if int(mech.get("level", -1)) != 0:
                continue
            with self.subTest(spell_id=spell_id):
                self.assertIn("cantrip_scaling", mech)
                self.assertNotIn("slot_scaling", mech)

    def test_slot_scaling_display_burning_hands(self):
        line = format_slot_scaling_summary(self.spell_entries["burning_hands"])
        self.assertIsNotNone(line)
        self.assertIn("Emplacement supérieur", line)
        self.assertIn("1d6", line)

    def test_slot_scaling_display_null_for_shield(self):
        self.assertIsNone(format_slot_scaling_summary(self.spell_entries["shield"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
