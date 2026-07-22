# tests/unit/test_lot6_druid.py
"""Lot 6 — Druide SRD 2014 (niv. 1–3)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import LevelUpPendingChoice, apply_level_up
from jdr_engine.rules.spellcasting.cast import cast_spell, get_spellcasting_stats
from jdr_engine.rules.spellcasting.preparation import druid_prepared_capacity
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
from jdr_engine.rules.spellcasting.state import (
    get_cantrips_known,
    get_spells_known,
    get_spells_prepared_list,
)
from tests.helpers.creation import druid_creation_kwargs


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestLot6Druid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_druid_level_1_spellcasting(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Rowan",
            engine=self.engine,
            **druid_creation_kwargs(level=1),
        )
        self.assertIn("spellcasting", char.choices)
        self.assertEqual(len(get_cantrips_known(char)), 2)
        self.assertIn("druidcraft", get_cantrips_known(char))
        self.assertIn("produce_flame", get_cantrips_known(char))
        sc = char.choices["spellcasting"]
        self.assertIn("spells_prepared", sc)
        self.assertNotIn("spells_known", sc)
        capacity = druid_prepared_capacity(2, 1)  # SAG 15 → mod +2
        prepared = get_spells_prepared_list(char)
        self.assertEqual(len(prepared), capacity)
        self.assertIn("entangle", prepared)
        self.assertIn("cure_wounds", prepared)
        self.assertIn("faerie_fire", prepared)
        self.assertNotIn("flaming_sphere", prepared)
        self.assertEqual(get_spells_known(char), prepared)

        mod, attack, save_dc = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod, 3)  # SAG effectif 16 (+3)
        self.assertEqual(save_dc, 13)
        self.assertEqual(attack, 5)

        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Préparation (affichage)", sheet.spellcasting_summary or "")
        self.assertTrue(
            any("Druidique" in line for line in sheet.class_features_lines)
        )

    def test_druid_level_up_circle_and_terrain(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Rowan",
            engine=self.engine,
            **druid_creation_kwargs(level=1),
        )
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        self.assertEqual(ctx.exception.pending.choice_type, "subclass")

        with self.assertRaises(LevelUpPendingChoice) as ctx2:
            apply_level_up(char, self.engine, subclass="land")
        self.assertEqual(ctx2.exception.pending.choice_type, "subchoice")
        self.assertEqual(ctx2.exception.pending.subchoice_storage_key, "druid_land_terrain")

        char, r2 = apply_level_up(
            char,
            self.engine,
            subclass="land",
            subchoice_value="forest",
        )
        self.assertEqual(r2.new_level, 2)
        self.assertEqual(char.choices.get("specialization"), "land")
        self.assertEqual(char.choices.get("druid_land_terrain"), "forest")

        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Forêt", sheet.specialization_label or "")
        self.assertTrue(
            any("Forme sauvage" in line for line in sheet.class_features_lines)
        )
        self.assertTrue(
            any("Terrain de cercle" in line for line in sheet.class_features_lines)
        )
        self.assertTrue(
            any("Récupération naturelle" in line for line in sheet.class_features_lines)
        )

    def test_druid_level_3_keeps_terrain_and_level_2_spells(self):
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
        char, r3 = apply_level_up(char, self.engine, subclass="land")
        self.assertEqual(r3.new_level, 3)
        self.assertEqual(char.choices.get("druid_land_terrain"), "forest")
        self.assertIn("flaming_sphere", get_spells_known(char))
        self.assertEqual(get_max_spell_slots("druid", 3).get(2), 2)

        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Forêt", sheet.specialization_label or "")

    def test_druid_cast_flaming_sphere(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Rowan",
            engine=self.engine,
            **druid_creation_kwargs(level=3),
        )
        from jdr_engine.rules.spellcasting.cast import build_spell_display_lines

        rng = SequenceRng([4, 5, 6])
        result = cast_spell(char, "flaming_sphere", self.engine, rng=rng, persist_slots=True)
        self.assertEqual(result.effect_type, "saving_throw")
        self.assertEqual(result.slot_consumed_level, 2)
        entry = self.engine.get_entity("spell", "flaming_sphere")
        lines = build_spell_display_lines(result, spell_mechanics=entry.definition.mechanics)
        text = "\n".join(lines)
        self.assertIn("Concentration", text)
        self.assertIn("Emplacement supérieur", text)

    def test_druid_cast_cure_wounds(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Rowan",
            engine=self.engine,
            **druid_creation_kwargs(level=1),
        )
        char.hp_current = 5
        result = cast_spell(char, "cure_wounds", self.engine, rng=lambda a, b: b)
        self.assertIsNotNone(result.healing_total)
        self.assertGreater(result.healing_total or 0, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
