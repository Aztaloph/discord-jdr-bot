# tests/unit/test_lot_a_cantrip_mechanics.py
"""Passe 1 / Lot A — métadonnées mécaniques des tours de magie SRD 2014."""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from jdr_engine.compendium.loader import load_ruleset
from jdr_engine.compendium.schemas.spell import SpellMechanics
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.mechanics_display import (
    build_spell_mechanics_reference_lines,
    format_cantrip_scaling_summary,
)

SRD_CANTrip_IDS: frozenset[str] = frozenset(
    {
        "druidcraft",
        "eldritch_blast",
        "fire_bolt",
        "guidance",
        "light",
        "mage_hand",
        "prestidigitation",
        "produce_flame",
        "ray_of_frost",
        "sacred_flame",
        "thaumaturgy",
        "vicious_mockery",
    }
)

OFFENSIVE_CANTrip_IDS: frozenset[str] = frozenset(
    {
        "eldritch_blast",
        "fire_bolt",
        "produce_flame",
        "ray_of_frost",
        "sacred_flame",
        "vicious_mockery",
    }
)

LOT_A_KEYS: frozenset[str] = frozenset(
    {
        "damage_dice",
        "damage_type",
        "save",
        "attack_roll",
        "cantrip_scaling",
        "description",
    }
)

REQUIRED_COMMON_KEYS: frozenset[str] = frozenset(
    {
        "casting_time",
        "range",
        "components",
        "duration",
        "attack_roll",
        "description",
    }
)


class TestLotACantripMechanics(unittest.TestCase):
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

    def test_all_compendium_cantrips_listed(self):
        cantrips = {
            sid
            for sid, mech in self.spell_entries.items()
            if int(mech.get("level", -1)) == 0
        }
        self.assertEqual(cantrips, SRD_CANTrip_IDS)

    def test_each_cantrip_validates_spell_mechanics_schema(self):
        for spell_id in SRD_CANTrip_IDS:
            with self.subTest(spell_id=spell_id):
                SpellMechanics.model_validate(self.spell_entries[spell_id])

    def test_offensive_cantrips_have_damage_and_scaling(self):
        for spell_id in OFFENSIVE_CANTrip_IDS:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                self.assertTrue(mech.get("damage_dice"), f"{spell_id}: damage_dice manquant")
                self.assertTrue(mech.get("damage_type"), f"{spell_id}: damage_type manquant")
                scaling = mech.get("cantrip_scaling")
                self.assertIsInstance(scaling, dict)
                tiers = scaling.get("tiers")
                self.assertEqual(len(tiers), 4)
                levels = [t["character_level"] for t in tiers]
                self.assertEqual(levels, [1, 5, 11, 17])

    def test_utility_cantrips_no_damage_scaling(self):
        for spell_id in SRD_CANTrip_IDS - OFFENSIVE_CANTrip_IDS:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                self.assertIsNone(mech.get("damage_dice"))
                self.assertIsNone(mech.get("cantrip_scaling"))

    def test_fire_bolt_scaling_dice_progression(self):
        mech = self.spell_entries["fire_bolt"]
        dice = [t["damage_dice"] for t in mech["cantrip_scaling"]["tiers"]]
        self.assertEqual(dice, ["1d10", "2d10", "3d10", "4d10"])

    def test_eldritch_blast_scaling_attacks_not_dice(self):
        mech = self.spell_entries["eldritch_blast"]
        tiers = mech["cantrip_scaling"]["tiers"]
        self.assertEqual([t["attacks"] for t in tiers], [1, 2, 3, 4])
        self.assertTrue(all(t["damage_dice"] == "1d10" for t in tiers))

    def test_common_mechanical_fields_on_all_cantrips(self):
        for spell_id in SRD_CANTrip_IDS:
            with self.subTest(spell_id=spell_id):
                mech = self.spell_entries[spell_id]
                for key in REQUIRED_COMMON_KEYS:
                    self.assertIn(key, mech, f"{spell_id}: {key} manquant")
                components = mech["components"]
                self.assertIsInstance(components, dict)
                self.assertIn("verbal", components)
                self.assertIn("somatic", components)
                self.assertIn("material", components)

    def test_level_two_plus_spells_not_lot_a_enriched(self):
        """Lots B/C enrichissent niv. 1–2 ; seul cantrip_scaling reste interdit hors cantrips."""
        for spell_id, mech in self.spell_entries.items():
            if int(mech.get("level", 0)) >= 2:
                with self.subTest(spell_id=spell_id):
                    self.assertNotIn(
                        "cantrip_scaling",
                        mech,
                        f"{spell_id} ne doit pas avoir cantrip_scaling",
                    )

    def test_level_two_plus_yaml_no_cantrip_scaling(self):
        spells_dir = Path("compendium/dnd5e/entries/spells")
        for spell_dir in spells_dir.iterdir():
            if not spell_dir.is_dir():
                continue
            raw = yaml.safe_load((spell_dir / "definition.yaml").read_text(encoding="utf-8"))
            level = int(raw["mechanics"]["level"])
            if level >= 2:
                with self.subTest(spell_id=raw["id"]):
                    self.assertNotIn("cantrip_scaling", raw["mechanics"])

    def test_mechanics_display_includes_scaling_for_fire_bolt(self):
        mech = self.spell_entries["fire_bolt"]
        summary = format_cantrip_scaling_summary(mech, character_level=1)
        self.assertIsNotNone(summary)
        self.assertIn("niv. 5", summary)
        self.assertIn("2d10", summary)

    def test_mechanics_reference_lines_for_guidance(self):
        lines = build_spell_mechanics_reference_lines(
            self.spell_entries["guidance"], locale="fr"
        )
        joined = "\n".join(lines)
        self.assertIn("Concentration", joined)
        self.assertIn("Composants", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
