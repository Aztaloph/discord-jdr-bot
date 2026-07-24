# tests/unit/test_spells_b2_schema.py
"""Lot B2 / B2-ter / B3-a / B3-b — schéma v2.0, effects[], pools dérivés du compendium."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.compendium.loader import load_ruleset
from jdr_engine.compendium.schemas.spell import SpellMechanics
from jdr_engine.rules.spellcasting.spell_pool_builder import build_class_spell_pools
from jdr_engine.rules.spellcasting.spells_catalog import (
    WIZARD_CANTRIP_IDS,
    WIZARD_SPELLBOOK_POOL,
    get_spell_ids_for_class,
)

CANONICAL_WIZARD_CANTrips = (
    "fire_bolt",
    "mage_hand",
    "light",
    "ray_of_frost",
)
CANONICAL_WIZARD_SPELLBOOK = (
    "mage_armor",
    "burning_hands",
    "detect_magic",
    "magic_missile",
    "shield",
    "scorching_ray",
    "darkness",
    "flaming_sphere",
    "fireball",
    "lightning_bolt",
    "counterspell",
    "dispel_magic",
    "fly",
    "haste",
    "polymorph",
    "banishment",
    "dimension_door",
    "ice_storm",
)

B3A_LEVEL_3_SPELL_IDS: frozenset[str] = frozenset(
    {
        "fireball",
        "lightning_bolt",
        "counterspell",
        "dispel_magic",
        "fly",
        "haste",
    }
)

B3B_LEVEL_4_SPELL_IDS: frozenset[str] = frozenset(
    {
        "polymorph",
        "banishment",
        "dimension_door",
        "ice_storm",
    }
)


class TestSpellsB2Schema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        _, _, entries = load_ruleset("dnd5e")
        cls.spell_entries = [
            entry for entry in entries if entry.definition.type == "spell"
        ]
        cls.spell_by_id = {entry.entry_id: entry for entry in cls.spell_entries}

    def test_all_spells_schema_version_two(self):
        for entry in self.spell_entries:
            with self.subTest(spell_id=entry.entry_id):
                self.assertEqual(entry.definition.schema_version, "2.0")

    def test_all_spells_have_classes_and_effects(self):
        for entry in self.spell_entries:
            with self.subTest(spell_id=entry.entry_id):
                self.assertTrue(entry.definition.classes)
                mechanics = SpellMechanics.model_validate(entry.definition.mechanics)
                self.assertGreaterEqual(len(mechanics.effects), 1)
                self.assertNotIn("effect", entry.definition.mechanics)

    def test_derived_wizard_pools_match_canonical_order(self):
        self.assertEqual(WIZARD_CANTRIP_IDS, CANONICAL_WIZARD_CANTrips)
        self.assertEqual(WIZARD_SPELLBOOK_POOL, CANONICAL_WIZARD_SPELLBOOK)
        self.assertEqual(len(WIZARD_CANTRIP_IDS), 4)
        self.assertEqual(len(WIZARD_SPELLBOOK_POOL), 18)

    def test_guidance_not_in_wizard_cantrip_pool(self):
        cantrips, _ = build_class_spell_pools()
        self.assertNotIn("guidance", cantrips.get("wizard", ()))
        self.assertNotIn("guidance", WIZARD_CANTRIP_IDS)

    def test_non_srd_wizard_cantrips_removed(self):
        for spell_id in ("thaumaturgy", "vicious_mockery"):
            with self.subTest(spell_id=spell_id):
                self.assertNotIn(spell_id, WIZARD_CANTRIP_IDS)

    def test_chromatic_orb_not_in_wizard_grimoire(self):
        self.assertNotIn("chromatic_orb", WIZARD_SPELLBOOK_POOL)

    def test_b3a_level_3_spells_validate_schema(self):
        for spell_id in B3A_LEVEL_3_SPELL_IDS:
            with self.subTest(spell_id=spell_id):
                entry = self.spell_by_id[spell_id]
                self.assertEqual(entry.definition.schema_version, "2.0")
                self.assertEqual(entry.definition.classes, ["wizard"])
                mechanics = SpellMechanics.model_validate(entry.definition.mechanics)
                self.assertEqual(mechanics.level, 3)

    def test_b3a_damage_spells_use_slot_scaling_metadata(self):
        for spell_id in ("fireball", "lightning_bolt"):
            with self.subTest(spell_id=spell_id):
                mech = self.spell_by_id[spell_id].definition.mechanics
                increment = mech["slot_scaling"]["per_slot_above_base"]
                self.assertEqual(increment.get("damage_dice"), "1d6")
                effect = mech["effects"][0]
                self.assertEqual(effect["type"], "saving_throw")
                self.assertEqual(effect["damage"], "8d6")

    def test_b3b_level_4_spells_validate_schema(self):
        for spell_id in B3B_LEVEL_4_SPELL_IDS:
            with self.subTest(spell_id=spell_id):
                entry = self.spell_by_id[spell_id]
                self.assertEqual(entry.definition.schema_version, "2.0")
                self.assertEqual(entry.definition.classes, ["wizard"])
                mechanics = SpellMechanics.model_validate(entry.definition.mechanics)
                self.assertEqual(mechanics.level, 4)

    def test_b3b_ice_storm_saving_throw_damage(self):
        mech = self.spell_by_id["ice_storm"].definition.mechanics
        effect = mech["effects"][0]
        self.assertEqual(effect["type"], "saving_throw")
        self.assertEqual(effect["damage"], "4d6+2d8")
        self.assertEqual(effect["saving_throw"]["ability"], "dex")
        self.assertTrue(effect["saving_throw"]["half_on_save"])

    def test_yaml_classes_match_derived_pools(self):
        cantrips, leveled = build_class_spell_pools()
        for entry in self.spell_entries:
            spell_id = entry.entry_id
            level = int(entry.definition.mechanics["level"])
            for class_id in entry.definition.classes:
                pool = cantrips.get(class_id, ()) if level == 0 else leveled.get(class_id, ())
                with self.subTest(spell_id=spell_id, class_id=class_id):
                    self.assertIn(spell_id, pool)
                    self.assertIn(spell_id, get_spell_ids_for_class(class_id))

    def test_vicious_mockery_multi_effect(self):
        entry = self.spell_by_id["vicious_mockery"]
        mechanics = SpellMechanics.model_validate(entry.definition.mechanics)
        self.assertEqual(len(mechanics.effects), 2)
        self.assertEqual(mechanics.effects[0].type, "saving_throw")
        self.assertIsNotNone(mechanics.effects[0].saving_throw)
        self.assertEqual(mechanics.effects[1].type, "utility")

    def test_utility_spells_with_save_sub_object(self):
        for spell_id in ("entangle", "faerie_fire"):
            with self.subTest(spell_id=spell_id):
                entry = self.spell_by_id[spell_id]
                mechanics = SpellMechanics.model_validate(entry.definition.mechanics)
                effect = mechanics.effects[0]
                self.assertEqual(effect.type, "utility")
                self.assertIsNotNone(effect.saving_throw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
