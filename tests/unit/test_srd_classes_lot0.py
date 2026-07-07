# tests/unit/test_srd_classes_lot0.py
"""Lot 0 — 12 classes SRD sélectionnables à la création."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet, parse_hit_die
from jdr_engine.rules.character_creation.class_choices import get_skill_choice_config
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_creation.playable import PLAYABLE_CLASSES, SRD_CLASSES
from jdr_engine.rules.derived_stats import get_class_saving_throw_proficiencies
from jdr_engine.rules.spellcasting.spells_catalog import (
    FULL_CASTER_CLASSES,
    HALF_CASTER_CLASSES,
    PACT_CASTER_CLASSES,
    SUPPORTED_SPELLCASTING_CLASSES,
)
from tests.helpers.creation import valid_point_buy_scores

# (class_id, hit_die, saves, hp_with_con_14, skill_count)
SRD_CLASS_EXPECTATIONS: tuple[tuple[str, str, frozenset[str], int, int], ...] = (
    ("barbarian", "d12", frozenset({"str", "con"}), 14, 2),
    ("bard", "d8", frozenset({"dex", "cha"}), 10, 3),
    ("cleric", "d8", frozenset({"wis", "cha"}), 10, 2),
    ("druid", "d8", frozenset({"int", "wis"}), 10, 2),
    ("fighter", "d10", frozenset({"str", "con"}), 12, 2),
    ("monk", "d8", frozenset({"str", "dex"}), 10, 2),
    ("paladin", "d10", frozenset({"wis", "cha"}), 12, 2),
    ("ranger", "d10", frozenset({"str", "dex"}), 12, 3),
    ("rogue", "d8", frozenset({"dex", "int"}), 10, 4),
    ("sorcerer", "d6", frozenset({"con", "cha"}), 9, 2),
    ("warlock", "d8", frozenset({"wis", "cha"}), 10, 2),
    ("wizard", "d6", frozenset({"int", "wis"}), 8, 2),
)


def _skills_for_class(engine: RuleEngine, class_id: str) -> list[str]:
    config = get_skill_choice_config(engine, class_id)
    if config is None:
        return []
    return list(config.options[: config.count])


class TestSrdClassesLot0(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_twelve_playable_classes(self):
        self.assertEqual(len(SRD_CLASSES), 12)
        self.assertEqual(PLAYABLE_CLASSES, SRD_CLASSES)

    def test_all_classes_in_compendium(self):
        for class_id in SRD_CLASSES:
            entry = self.engine.get_entity("class", class_id)
            self.assertIsNotNone(entry, msg=f"missing class {class_id}")

    def test_each_class_base_stats(self):
        for (
            class_id,
            expected_die,
            expected_saves,
            expected_hp,
            skill_count,
        ) in SRD_CLASS_EXPECTATIONS:
            with self.subTest(class_id=class_id):
                skills = _skills_for_class(self.engine, class_id)
                kwargs: dict = dict(
                    name=f"Test-{class_id}",
                    race_id="human",
                    class_id=class_id,
                    owner_id="1",
                    guild_id="1",
                    base_scores=valid_point_buy_scores(con=14),
                    engine=self.engine,
                    skills=skills,
                )
                if class_id == "fighter":
                    kwargs["fighting_style"] = "defense"
                if class_id == "rogue":
                    kwargs["expertise_skills"] = list(skills[:2])
                if class_id == "cleric":
                    kwargs["specialization"] = "life"
                if class_id == "sorcerer":
                    kwargs["specialization"] = "draconic"
                    kwargs["sorcerer_dragon_type"] = "red"
                if class_id == "ranger":
                    kwargs["favored_enemy_type"] = "beasts"
                    kwargs["favored_terrain"] = "forest"
                if class_id == "warlock":
                    kwargs["specialization"] = "fiend"

                char = finalize_new_character(**kwargs)
                sheet = build_character_sheet(char, self.engine)

                hit_die = self.engine.get_class_hit_die(class_id)
                self.assertEqual(hit_die, expected_die)
                self.assertEqual(parse_hit_die(hit_die or "d8"), int(expected_die[1:]))
                self.assertEqual(
                    get_class_saving_throw_proficiencies(self.engine, class_id),
                    expected_saves,
                )
                self.assertEqual(sheet.hp_max, expected_hp)
                self.assertEqual(sheet.hit_die, expected_die)
                self.assertEqual(len(sheet.proficient_skill_labels), skill_count)
                self.assertTrue(sheet.armor_proficiencies_text)
                self.assertTrue(sheet.weapon_proficiencies_text)

                if class_id in FULL_CASTER_CLASSES:
                    self.assertIn("spellcasting", char.choices)
                elif class_id in PACT_CASTER_CLASSES:
                    self.assertIn("spellcasting", char.choices)
                elif class_id in HALF_CASTER_CLASSES:
                    self.assertNotIn("spellcasting", char.choices or {})
                else:
                    self.assertNotIn("spellcasting", char.choices or {})

    def test_wizard_unchanged_spellcasting(self):
        char = finalize_new_character(
            name="Merlin",
            race_id="human",
            class_id="wizard",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(int=15, con=14),
            engine=self.engine,
            skills=["arcana", "history"],
        )
        sc = char.choices["spellcasting"]
        self.assertIn("fire_bolt", sc["cantrips_known"])
        self.assertEqual(len(sc["spellbook"]), 6)
        self.assertIn("burning_hands", sc["spells_prepared"])
        self.assertIn("burning_hands", sc["spellbook"])

    def test_cleric_unchanged_domain_and_spells(self):
        char = finalize_new_character(
            name="Clerc",
            race_id="human",
            class_id="cleric",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(wis=15, con=14),
            engine=self.engine,
            skills=["medicine", "religion"],
            specialization="life",
        )
        self.assertEqual(char.choices.get("specialization"), "life")
        self.assertIn("sacred_flame", char.choices["spellcasting"]["cantrips_known"])

    def test_fighter_saving_throw_proficiency_on_sheet(self):
        char = finalize_new_character(
            name="Guerrier",
            race_id="human",
            class_id="fighter",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(str=15, con=14),
            engine=self.engine,
            skills=["athletics", "perception"],
            fighting_style="defense",
        )
        sheet = build_character_sheet(char, self.engine)
        saves = " ".join(sheet.saving_throws)
        self.assertIn("FOR", saves)
        self.assertIn("CON", saves)
        self.assertIn("●", saves)
        self.assertIn("Armures lourdes", sheet.armor_proficiencies_text)

    def test_paladin_spellcasting_starts_level_2(self):
        char = finalize_new_character(
            name="Paladin",
            race_id="human",
            class_id="paladin",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(cha=15, con=14),
            engine=self.engine,
            skills=["athletics", "religion"],
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertIsNotNone(sheet.spellcasting_summary)
        assert sheet.spellcasting_summary is not None
        self.assertIn("niv. 2", sheet.spellcasting_summary)

    def test_warlock_pact_magic_not_full_caster(self):
        char = finalize_new_character(
            name="Occultiste",
            race_id="human",
            class_id="warlock",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(cha=15, con=14),
            engine=self.engine,
            skills=["arcana", "deception"],
            specialization="fiend",
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertIn("spellcasting", char.choices)
        self.assertNotIn("warlock", FULL_CASTER_CLASSES)
        self.assertIsNotNone(sheet.spellcasting_summary)
        assert sheet.spellcasting_summary is not None
        self.assertIn("Magie de pacte", sheet.spellcasting_summary)
        self.assertIn("repos court", sheet.spellcasting_summary)
        entry = self.engine.get_entity("class", "warlock")
        assert entry is not None
        mechanics = entry.definition.mechanics
        self.assertIn("pact_magic", mechanics)
        self.assertNotIn("spellcasting", mechanics)


if __name__ == "__main__":
    unittest.main(verbosity=2)
