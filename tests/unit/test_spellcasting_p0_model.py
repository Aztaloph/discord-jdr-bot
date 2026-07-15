# tests/unit/test_spellcasting_p0_model.py
"""Passe 2 / Lot P0 — taxonomie lanceurs et filtres pools (sans breaking change)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.model import (
    KNOWN_FIXED_CLASSES,
    PREPARED_CLASSES,
    RANGER_SPELLS_KNOWN_BY_LEVEL,
    SORCERER_SPELLS_KNOWN_BY_LEVEL,
    WARLOCK_SPELLS_KNOWN_BY_LEVEL,
    SpellcastingFamily,
    cantrips_known_capacity,
    casting_ability_for_class,
    cleric_prepared_capacity,
    druid_prepared_capacity,
    get_spellcasting_family,
    is_known_fixed_caster,
    is_prepared_caster,
    is_wizard_hybrid_caster,
    paladin_prepared_capacity,
    prepared_capacity_for_class,
    spellbook_capacity,
    spells_known_capacity,
    wizard_prepared_capacity,
)
from jdr_engine.rules.spellcasting.pools import (
    filter_spells_by_max_level,
    get_cantrip_pool,
    get_filtered_leveled_pool,
    get_leveled_spell_pool,
    max_castable_spell_level,
    spell_id_in_class_pool,
)
from jdr_engine.rules.spellcasting.preparation import (
    BARD_CANTRIPS_BY_LEVEL,
    WIZARD_SPELLBOOK_BY_LEVEL,
)
from jdr_engine.rules.spellcasting.spell_levels import get_spell_level, reset_spell_level_cache
from jdr_engine.rules.spellcasting.spells_catalog import SUPPORTED_SPELLCASTING_CLASSES


class TestSpellcastingTaxonomy(unittest.TestCase):
    def test_all_supported_classes_have_family(self):
        for class_id in SUPPORTED_SPELLCASTING_CLASSES:
            with self.subTest(class_id=class_id):
                family = get_spellcasting_family(class_id)
                self.assertIsNotNone(family)

    def test_ranger_and_paladin_prepared_family(self):
        self.assertIn("ranger", PREPARED_CLASSES)
        self.assertIn("paladin", PREPARED_CLASSES)
        self.assertNotIn("ranger", KNOWN_FIXED_CLASSES)
        self.assertEqual(get_spellcasting_family("ranger"), SpellcastingFamily.PREPARED)
        self.assertEqual(get_spellcasting_family("paladin"), SpellcastingFamily.PREPARED)

    def test_wizard_hybrid(self):
        self.assertTrue(is_wizard_hybrid_caster("wizard"))
        self.assertFalse(is_wizard_hybrid_caster("sorcerer"))
        self.assertEqual(get_spellcasting_family("wizard"), SpellcastingFamily.WIZARD_HYBRID)

    def test_known_fixed_classes(self):
        for cid in ("bard", "sorcerer", "warlock"):
            self.assertTrue(is_known_fixed_caster(cid))
            self.assertFalse(is_prepared_caster(cid))

    def test_prepared_classes(self):
        for cid in ("cleric", "druid", "ranger", "paladin"):
            self.assertTrue(is_prepared_caster(cid))
            self.assertFalse(is_known_fixed_caster(cid))

    def test_casting_abilities(self):
        self.assertEqual(casting_ability_for_class("wizard"), "int")
        self.assertEqual(casting_ability_for_class("cleric"), "wis")
        self.assertEqual(casting_ability_for_class("paladin"), "cha")
        self.assertEqual(casting_ability_for_class("ranger"), "wis")
        self.assertEqual(casting_ability_for_class("bard"), "cha")


class TestSpellcastingCapacities(unittest.TestCase):
    def test_cleric_druid_wizard_prepared_capacity(self):
        self.assertEqual(cleric_prepared_capacity(2, 3), 5)
        self.assertEqual(druid_prepared_capacity(2, 3), 5)
        self.assertEqual(wizard_prepared_capacity(3, 3), 6)

    def test_paladin_prepared_capacity_srd(self):
        self.assertEqual(paladin_prepared_capacity(3, 2), 4)  # CHA +1, niv.2 → 1+1
        self.assertEqual(paladin_prepared_capacity(2, 3), 3)  # mod +2, niv.3 → 2+1
        self.assertEqual(prepared_capacity_for_class("paladin", 2, 3), 3)

    def test_known_fixed_quotas(self):
        self.assertEqual(spells_known_capacity("sorcerer", 1), 2)
        self.assertEqual(spells_known_capacity("warlock", 3), WARLOCK_SPELLS_KNOWN_BY_LEVEL[3])
        self.assertEqual(spells_known_capacity("ranger", 2), 0)
        self.assertEqual(spells_known_capacity("cleric", 1), 0)

    def test_cantrip_and_spellbook_capacity(self):
        self.assertEqual(cantrips_known_capacity("wizard", 3), 4)
        self.assertEqual(spellbook_capacity("wizard", 3), WIZARD_SPELLBOOK_BY_LEVEL[3])
        self.assertEqual(cantrips_known_capacity("bard", 1), BARD_CANTRIPS_BY_LEVEL[1])


class TestSpellLevelsFromCompendium(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def setUp(self):
        reset_spell_level_cache()

    def test_cantrip_and_leveled_spells(self):
        self.assertEqual(get_spell_level("fire_bolt", engine=self.engine), 0)
        self.assertEqual(get_spell_level("magic_missile", engine=self.engine), 1)
        self.assertEqual(get_spell_level("scorching_ray", engine=self.engine), 2)

    def test_unknown_defaults_to_one(self):
        self.assertEqual(get_spell_level("nonexistent_spell_xyz"), 1)


class TestSpellPools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_wizard_leveled_pool_excludes_cantrips(self):
        leveled = get_leveled_spell_pool("wizard")
        cantrips = set(get_cantrip_pool("wizard"))
        self.assertNotIn("fire_bolt", leveled)
        self.assertIn("magic_missile", leveled)
        self.assertTrue(cantrips.isdisjoint(set(leveled)))

    def test_ranger_and_paladin_pools_distinct(self):
        ranger = get_leveled_spell_pool("ranger")
        paladin = get_leveled_spell_pool("paladin")
        self.assertIn("hunters_mark", ranger)
        self.assertNotIn("hunters_mark", paladin)
        self.assertIn("bless", paladin)

    def test_filter_by_max_level_wizard_level_1(self):
        pool = get_leveled_spell_pool("wizard")
        filtered = filter_spells_by_max_level(pool, 1, engine=self.engine)
        self.assertIn("magic_missile", filtered)
        self.assertNotIn("scorching_ray", filtered)

    def test_filtered_leveled_pool_druid_level_3(self):
        pool = get_filtered_leveled_pool("druid", 3, engine=self.engine)
        self.assertIn("flaming_sphere", pool)
        self.assertEqual(max_castable_spell_level("druid", 3), 2)

    def test_spell_in_class_pool(self):
        self.assertTrue(spell_id_in_class_pool("cleric", "cure_wounds"))
        self.assertFalse(spell_id_in_class_pool("ranger", "bless"))


class TestPreparationRetrocompatImports(unittest.TestCase):
    """Les symboles réexportés depuis model restent importables via preparation."""

    def test_preparation_reexports_model_constants(self):
        from jdr_engine.rules.spellcasting import preparation as prep

        self.assertEqual(prep.BARD_CANTRIPS_BY_LEVEL[1], 2)
        self.assertEqual(prep.SORCERER_SPELLS_KNOWN_BY_LEVEL[1], 2)
        self.assertEqual(prep.cleric_prepared_capacity(1, 1), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
