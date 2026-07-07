# tests/unit/test_lot1_martial.py
"""Lot 1 — Guerrier & Barbare SRD 2014 (niv. 1–3, sous-classes)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import (
    LevelUpPendingChoice,
    apply_level_up,
)
from jdr_engine.rules.class_features.barbarian import (
    can_start_rage,
    rage_uses_max,
    rage_uses_remaining,
    start_rage,
    totem_bear_resistances_active,
)
from jdr_engine.rules.class_features.fighter import (
    defense_ac_bonus,
    dueling_damage_bonus,
    improved_critical_range,
    roll_second_wind_healing,
    second_wind_available,
    use_second_wind,
)
from tests.helpers.creation import (
    barbarian_creation_kwargs,
    fighter_creation_kwargs,
    valid_point_buy_scores,
)


class TestLot1Barbarian(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_level_3_berserker_creation(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Grunt",
            engine=self.engine,
            **barbarian_creation_kwargs(
                level=3,
                specialization="berserker",
            ),
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(char.level, 3)
        self.assertEqual(char.choices["specialization"], "berserker")
        self.assertEqual(rage_uses_max(3), 3)
        self.assertEqual(rage_uses_remaining(char.choices, level=3), 3)
        self.assertTrue(any("Rage" in line for line in sheet.class_features_lines))
        self.assertTrue(any("Frénésie" in line for line in sheet.class_features_lines))

    def test_unarmored_defense_ac(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Grunt",
            engine=self.engine,
            **barbarian_creation_kwargs(level=1),
        )
        sheet = build_character_sheet(char, self.engine)
        # CON 14 (+2), DEX 10 (+0) → 10+0+2 = 12
        self.assertEqual(sheet.ac, 12)

    def test_rage_counter_and_start(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Grunt",
            engine=self.engine,
            **barbarian_creation_kwargs(level=1),
        )
        self.assertTrue(can_start_rage(char.choices, level=1))
        char.choices = start_rage(char.choices, level=1)
        self.assertEqual(rage_uses_remaining(char.choices, level=1), 1)
        self.assertTrue(char.choices["feature_state"]["rage_active"])

    def test_level_3_totem_bear(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Totem",
            engine=self.engine,
            **barbarian_creation_kwargs(
                level=3,
                specialization="totem_warrior",
                totem_spirit="bear",
            ),
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(char.choices.get("totem_spirit"), "bear")
        self.assertIn("Guerrier totémique", sheet.class_display)
        self.assertIn("ours", sheet.class_display.lower())
        self.assertTrue(
            totem_bear_resistances_active(
                char.choices,
                rage_is_active=True,
            )
        )

    def test_level_up_to_3_pending_subclass(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Grunt",
            engine=self.engine,
            **barbarian_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        self.assertEqual(ctx.exception.pending.choice_type, "subclass")
        self.assertIn("berserker", ctx.exception.pending.options)


class TestLot1Fighter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_defense_style_ac_bonus(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Tank",
            engine=self.engine,
            **fighter_creation_kwargs(fighting_style="defense"),
        )
        sheet = build_character_sheet(char, self.engine)
        # DEX 8 (-1), style Défense +1 en armure → 10 + (-1) + 1 = 10
        self.assertEqual(sheet.ac, 10)
        self.assertEqual(defense_ac_bonus(char.choices, wearing_armor=True), 1)

    def test_dueling_damage_bonus(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Duel",
            engine=self.engine,
            **fighter_creation_kwargs(fighting_style="dueling"),
        )
        self.assertEqual(dueling_damage_bonus(char.choices, one_handed_melee=True), 2)
        self.assertEqual(dueling_damage_bonus(char.choices, one_handed_melee=False), 0)

    def test_second_wind_healing_and_counter(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Heal",
            engine=self.engine,
            **fighter_creation_kwargs(level=1),
        )
        self.assertTrue(second_wind_available(char.choices))
        total, _ = roll_second_wind_healing(3)
        self.assertGreaterEqual(total, 4)
        char.choices = use_second_wind(char.choices)
        self.assertFalse(second_wind_available(char.choices))

    def test_level_3_champion_critical(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Champ",
            engine=self.engine,
            **fighter_creation_kwargs(
                level=3,
                specialization="champion",
            ),
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(char.choices["specialization"], "champion")
        self.assertEqual(improved_critical_range(char.choices, level=3), (19, 20))
        self.assertTrue(any("19-20" in line for line in sheet.class_features_lines))
        self.assertIn("Champion", sheet.class_display)

    def test_fighter_requires_fighting_style(self):
        with self.assertRaises(ValueError):
            finalize_new_character(
                owner_id="1",
                guild_id="1",
                name="Bad",
                race_id="human",
                class_id="fighter",
                base_scores=valid_point_buy_scores(con=14),
                engine=self.engine,
                skills=["athletics", "perception"],
            )

    def test_level_up_champion(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Champ",
            engine=self.engine,
            **fighter_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        char, result = apply_level_up(char, self.engine, subclass="champion")
        self.assertEqual(result.new_level, 3)
        self.assertEqual(char.choices["specialization"], "champion")


class TestLot1NonRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_wizard_still_works(self):
        from tests.helpers.creation import wizard_creation_kwargs

        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Wiz",
            engine=self.engine,
            **wizard_creation_kwargs(),
        )
        self.assertIn("fire_bolt", char.choices["spellcasting"]["cantrips_known"])

    def test_cleric_still_works(self):
        from tests.helpers.creation import cleric_creation_kwargs

        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Clerc",
            engine=self.engine,
            **cleric_creation_kwargs(),
        )
        self.assertEqual(char.choices["specialization"], "life")


if __name__ == "__main__":
    unittest.main(verbosity=2)
