# tests/unit/test_lot7_warlock.py
"""Lot 7 — Occultiste SRD 2014 (niv. 1–3)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import LevelUpPendingChoice, apply_level_up
from jdr_engine.rules.rest import apply_short_rest
from jdr_engine.rules.spellcasting.cast import SpellCastError, cast_spell, get_spellcasting_stats
from jdr_engine.rules.spellcasting.model import spells_known_capacity
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots, get_remaining_slots
from jdr_engine.rules.spellcasting.spells_catalog import FULL_CASTER_CLASSES
from jdr_engine.rules.spellcasting.state import (
    consume_spell_slot,
    get_cantrips_known,
    get_slots_used,
    get_spells_known,
)
from tests.helpers.creation import warlock_creation_kwargs


class TestLot7Warlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_warlock_not_full_caster(self):
        self.assertNotIn("warlock", FULL_CASTER_CLASSES)

    def test_warlock_level_1_pact_magic(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=1),
        )
        self.assertEqual(char.choices.get("specialization"), "fiend")
        self.assertIn("spellcasting", char.choices)
        self.assertEqual(get_max_spell_slots("warlock", 1), {1: 1})
        self.assertEqual(len(get_cantrips_known(char)), 2)
        self.assertIn("eldritch_blast", get_cantrips_known(char))
        known = get_spells_known(char)
        self.assertIn("hex", known)
        self.assertIn("armor_of_agathys", known)
        self.assertNotIn("darkness", known)

        mod, attack, save_dc = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod, 2)
        self.assertEqual(save_dc, 12)
        self.assertEqual(attack, 4)

        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Magie de pacte", sheet.spellcasting_summary or "")
        self.assertIn("repos court", sheet.spellcasting_summary or "")
        self.assertTrue(
            any("Bénédiction du Ténébreux" in line for line in sheet.class_features_lines)
        )

    def test_warlock_level_up_invocations(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=1),
        )
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        self.assertEqual(ctx.exception.pending.choice_type, "eldritch_invocations")

        char, r2 = apply_level_up(
            char,
            self.engine,
            eldritch_invocations=["agonizing_blast", "devils_sight"],
        )
        self.assertEqual(r2.new_level, 2)
        self.assertEqual(
            char.choices.get("eldritch_invocations"),
            ["agonizing_blast", "devils_sight"],
        )
        self.assertEqual(get_max_spell_slots("warlock", 2), {1: 2})
        known = get_spells_known(char)
        self.assertEqual(len(known), spells_known_capacity("warlock", 2))
        self.assertIn("darkness", known)

        sheet = build_character_sheet(char, self.engine)
        self.assertTrue(
            any("Manifestations occultes" in line for line in sheet.class_features_lines)
        )

    def test_warlock_level_3_pact_boon_and_slots(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(
            char,
            self.engine,
            eldritch_invocations=["agonizing_blast", "eldritch_spear"],
        )
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        self.assertEqual(ctx.exception.pending.choice_type, "pact_boon")

        char, r3 = apply_level_up(
            char,
            self.engine,
            eldritch_invocations=["agonizing_blast", "eldritch_spear"],
            pact_boon="pact_of_the_chain",
        )
        self.assertEqual(r3.new_level, 3)
        self.assertEqual(char.choices.get("pact_boon"), "pact_of_the_chain")
        self.assertEqual(
            char.choices.get("eldritch_invocations"),
            ["agonizing_blast", "eldritch_spear"],
        )
        self.assertEqual(get_max_spell_slots("warlock", 3), {2: 2})
        self.assertIn("darkness", get_spells_known(char))

    def test_short_rest_recharges_pact_slots(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=2),
        )
        char = consume_spell_slot(char, 1)
        self.assertEqual(get_slots_used(char).get(1, 0), 1)
        char, _ = apply_short_rest(char, self.engine, dice_to_spend=0)
        remaining = get_remaining_slots("warlock", 2, get_slots_used(char))
        self.assertEqual(remaining[1], 2)

    def test_eldritch_blast_with_agonizing_blast(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=2),
        )
        result = cast_spell(char, "eldritch_blast", self.engine, rng=lambda a, b: b)
        self.assertEqual(result.damage_total, 10 + 2)

    def test_eldritch_blast_without_agonizing_blast(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(
                level=2,
                eldritch_invocations=["devils_sight", "eldritch_sight"],
            ),
        )
        result = cast_spell(char, "eldritch_blast", self.engine, rng=lambda a, b: b)
        self.assertEqual(result.damage_total, 10)

    def test_warlock_level_2_knows_darkness_but_cannot_cast(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=2),
        )
        self.assertIn("darkness", get_spells_known(char))
        with self.assertRaises(SpellCastError):
            cast_spell(char, "darkness", self.engine, persist_slots=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
