# tests/unit/test_lot3_halfcasters.py
"""Lot 3 — Rôdeur & Paladin SRD 2014 (demi-lanceurs niv. 1–3)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import LevelUpPendingChoice, apply_level_up
from jdr_engine.rules.class_features.paladin import (
    apply_divine_smite,
    divine_sense_uses_max,
    lay_on_hands_pool_max,
    lay_on_hands_remaining,
    spend_lay_on_hands,
)
from jdr_engine.rules.spellcasting.access import has_spellcasting_access
from jdr_engine.rules.spellcasting.cast import SpellCastError, cast_spell, get_spellcasting_stats
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
from jdr_engine.rules.spellcasting.state import (
    get_slots_used,
    get_spells_known,
    get_spells_prepared_list,
    list_castable_spell_ids,
)
from tests.helpers.creation import (
    barbarian_creation_kwargs,
    monk_creation_kwargs,
    paladin_creation_kwargs,
    ranger_creation_kwargs,
    rogue_creation_kwargs,
    wizard_creation_kwargs,
)


class TestLot3RogueLore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_rogue_lore_not_ranger_text(self):
        lore = self.engine.presenter.get_lore("class", "rogue", locale="fr")
        self.assertIn("roublard", lore.lower())
        self.assertIn("attaque sournoise", lore.lower())
        self.assertNotIn("rôdeur traque", lore.lower())


class TestLot3Ranger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_level_1_spells_visible_no_slots(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Aragorn",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        self.assertTrue(has_spellcasting_access(char, self.engine))
        self.assertEqual(get_max_spell_slots("ranger", 1), {})
        self.assertIn("spellcasting", char.choices)
        sc = char.choices["spellcasting"]
        self.assertIn("spells_prepared", sc)
        self.assertNotIn("spells_known", sc)
        self.assertIn("hunters_mark", list_castable_spell_ids(char))
        with self.assertRaises(SpellCastError) as ctx:
            cast_spell(char, "hunters_mark", self.engine, persist_slots=False)
        self.assertIn("emplacement", str(ctx.exception).lower())

    def test_level_up_to_2_grants_half_caster(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Aragorn",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        self.assertEqual(ctx.exception.pending.choice_type, "fighting_style")

        char, result = apply_level_up(char, self.engine, fighting_style="archery")
        self.assertEqual(result.new_level, 2)
        self.assertTrue(has_spellcasting_access(char, self.engine))
        self.assertEqual(get_max_spell_slots("ranger", 2), {1: 2})
        prepared = get_spells_prepared_list(char)
        self.assertEqual(len(prepared), 2)
        self.assertIn("hunters_mark", prepared)
        self.assertEqual(get_spells_known(char), prepared)

        mod, atk, dc = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod, 3)  # SAG 15 base + humain +1 → effectif 16 (+3)
        sheet = build_character_sheet(char, self.engine)
        self.assertTrue(any("Ennemi juré" in line for line in sheet.class_features_lines))
        self.assertTrue(any("archery" in line.lower() or "Archerie" in line for line in sheet.class_features_lines))

    def test_level_up_to_3_hunter_prey(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Tracker",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, fighting_style="dueling")
        with self.assertRaises(LevelUpPendingChoice):
            apply_level_up(char, self.engine)
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine, subclass="hunter")
        self.assertEqual(ctx.exception.pending.choice_type, "subchoice")
        char, result = apply_level_up(
            char, self.engine, subclass="hunter", subchoice_value="colossus_slayer"
        )
        self.assertEqual(result.new_level, 3)
        self.assertEqual(char.choices.get("hunter_prey"), "colossus_slayer")
        self.assertEqual(len(get_spells_prepared_list(char)), 3)
        sheet = build_character_sheet(char, self.engine)
        primeval = [line for line in sheet.class_features_lines if "Conscience primitive" in line]
        self.assertEqual(len(primeval), 1)
        self.assertTrue(any("Tueur de colosses" in line for line in sheet.class_features_lines))


class TestLot3Paladin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_lay_on_hands_pool_level_1(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=1),
        )
        self.assertEqual(lay_on_hands_pool_max(1), 5)
        self.assertEqual(lay_on_hands_remaining(char.choices or {}, level=1), 5)
        max_ds = divine_sense_uses_max(14)  # CHA 14 → +2 → 3 uses
        sheet = build_character_sheet(char, self.engine)
        self.assertTrue(
            any(f"Sens divin" in line and f"/{max_ds}" in line for line in sheet.class_features_lines)
        )

    def test_partial_lay_on_hands_spend(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=1),
        )
        choices = spend_lay_on_hands(char.choices or {}, level=1, amount=3)
        self.assertEqual(lay_on_hands_remaining(choices, level=1), 2)

    def test_level_2_spellcasting_and_smite(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, fighting_style="defense")
        self.assertTrue(has_spellcasting_access(char, self.engine))
        mod, _, _ = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod, 2)  # CHA 14
        self.assertEqual(get_max_spell_slots("paladin", 2), {1: 2})

        updated = apply_divine_smite(char, slot_level=1)
        used = get_slots_used(updated)
        self.assertEqual(sum(used.values()), 1)

    def test_level_3_devotion(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, fighting_style="defense")
        char, _ = apply_level_up(char, self.engine, subclass="devotion")
        self.assertEqual(lay_on_hands_pool_max(3), 15)
        self.assertEqual(lay_on_hands_remaining(char.choices or {}, level=3), 15)
        sheet = build_character_sheet(char, self.engine)
        self.assertTrue(any("Santé divine" in line for line in sheet.class_features_lines))
        self.assertTrue(any("Arme sacrée" in line for line in sheet.class_features_lines))
        self.assertTrue(any("Canalisation" in line for line in sheet.class_features_lines))

    def test_paladin_level_3_embed_fields_valid(self):
        from interfaces.discord.formatters.character_embed import build_character_display
        from interfaces.discord.formatters.embed_fields import DISCORD_FIELD_VALUE_MAX

        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, fighting_style="defense")
        char, _ = apply_level_up(char, self.engine, subclass="devotion")
        sheet = build_character_sheet(char, self.engine)
        embed = build_character_display(sheet, self.engine, include_lore=False).embed
        for field in embed.fields:
            self.assertLessEqual(len(field.value), DISCORD_FIELD_VALUE_MAX)
        aptitude_names = [f.name for f in embed.fields if "Aptitudes" in f.name]
        self.assertTrue(aptitude_names)


class TestLot3NonRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_wizard_still_casts(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Mage",
            engine=self.engine,
            **wizard_creation_kwargs(),
        )
        result = cast_spell(char, "fire_bolt", self.engine, persist_slots=False)
        self.assertEqual(result.spell_id, "fire_bolt")

    def test_rogue_level_1_unchanged(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Rogue",
            engine=self.engine,
            **rogue_creation_kwargs(level=1),
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertTrue(any("Attaque sournoise" in line for line in sheet.class_features_lines))

    def test_barbarian_monk_still_level_up(self):
        barb = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="B",
            engine=self.engine,
            **barbarian_creation_kwargs(level=1),
        )
        barb, r = apply_level_up(barb, self.engine)
        self.assertEqual(r.new_level, 2)

        monk = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="M",
            engine=self.engine,
            **monk_creation_kwargs(level=1),
        )
        monk, r2 = apply_level_up(monk, self.engine)
        self.assertEqual(r2.new_level, 2)

    def test_ranger_level_1_no_slot_error(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="R",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        with self.assertRaises(SpellCastError) as ctx:
            cast_spell(char, "hunters_mark", self.engine, persist_slots=False)
        self.assertIn("emplacement", str(ctx.exception).lower())

    def test_ranger_legacy_level_1_no_spellcasting_still_blocked(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Legacy",
            engine=self.engine,
            **ranger_creation_kwargs(level=1),
        )
        del char.choices["spellcasting"]
        with self.assertRaises(SpellCastError) as ctx:
            cast_spell(char, "hunters_mark", self.engine, persist_slots=False)
        self.assertIn("accès", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
