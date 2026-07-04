# tests/unit/test_srd_races.py
"""Races SRD 2014 — Drakéide, Gnome, Demi-elfe, Demi-orc, Tieffelin."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import CharacterService
from jdr_engine.dice.d20 import D20RollRequest
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine, roll_d20_for_character
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_creation.playable import PLAYABLE_RACES
from jdr_engine.rules.racial.breath_weapon import use_breath_weapon
from jdr_engine.rules.racial.features import relentless_endurance_available
from jdr_engine.rules.racial.resolve import (
    get_damage_resistances,
    get_racial_ability_bonuses,
    resolve_race_trait_labels,
)

from tests.helpers.creation import valid_point_buy_scores, wizard_creation_kwargs


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestPlayableRaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_all_nine_races_in_compendium(self):
        for race_id in PLAYABLE_RACES:
            self.assertIsNotNone(
                self.engine.get_entity("race", race_id),
                msg=f"race {race_id} missing",
            )

    def test_existing_races_unchanged_count(self):
        self.assertEqual(len(PLAYABLE_RACES), 9)


class TestDragonborn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_creation_red_ancestry(self):
        char = finalize_new_character(
            name="Drake",
            race_id="dragonborn",
            class_id="wizard",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(str=15, cha=14, con=14),
            engine=self.engine,
            skills=["arcana", "history"],
            draconic_ancestry="red",
        )
        self.assertEqual(char.choices.get("draconic_ancestry"), "red")
        bonuses = get_racial_ability_bonuses(char, self.engine)
        self.assertEqual(bonuses.get("str"), 2)
        self.assertEqual(bonuses.get("cha"), 1)
        self.assertEqual(get_damage_resistances(char), ("fire",))

    def test_trait_labels_gold_ancestry_no_duplicate(self):
        char = finalize_new_character(
            name="Drake",
            race_id="dragonborn",
            class_id="wizard",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(str=15, cha=14, con=14),
            engine=self.engine,
            skills=["arcana", "history"],
            draconic_ancestry="gold",
        )
        labels = resolve_race_trait_labels(char, self.engine)
        self.assertEqual(
            labels,
            [
                "Ascendance draconique (Or)",
                "Souffle draconique",
                "Résistance draconique",
            ],
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(sheet.trait_names, labels)
        self.assertNotIn("Ascendance Or", sheet.trait_names)

    def test_breath_weapon_red(self):
        char = finalize_new_character(
            name="Drake",
            race_id="dragonborn",
            class_id="wizard",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(str=15, cha=14, con=14),
            engine=self.engine,
            skills=["arcana", "history"],
            draconic_ancestry="red",
        )
        result = use_breath_weapon(char, self.engine)
        self.assertEqual(result.ancestry_label, "Rouge")
        self.assertEqual(result.damage_type, "fire")
        self.assertEqual(result.shape, "cône")
        self.assertEqual(result.damage_dice, "2d6")
        self.assertGreaterEqual(result.save_dc, 10)


class TestHalfElf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_flexible_asi_and_skills(self):
        char = finalize_new_character(
            name="Elara",
            race_id="half_elf",
            class_id="wizard",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(int=15, cha=8),
            engine=self.engine,
            skills=["arcana", "history"],
            racial_ability_bonuses=["str", "int"],
            racial_skills=["perception", "stealth"],
        )
        bonuses = get_racial_ability_bonuses(char, self.engine)
        self.assertEqual(bonuses.get("cha"), 2)
        self.assertEqual(bonuses.get("str"), 1)
        self.assertEqual(bonuses.get("int"), 1)
        sheet = build_character_sheet(char, self.engine)
        skill_text = " ".join(sheet.proficient_skill_labels)
        self.assertIn("Perception", skill_text)
        self.assertIn("Discrétion", skill_text)

    def test_fey_ancestry_advantage(self):
        char = finalize_new_character(
            name="Elara",
            race_id="half_elf",
            class_id="wizard",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(),
            engine=self.engine,
            skills=["arcana", "history"],
            racial_ability_bonuses=["str", "dex"],
            racial_skills=["medicine", "religion"],
        )
        result = roll_d20_for_character(
            D20RollRequest(
                roll_type="saving_throw",
                save_versus_condition="charmed",
                ability_modifier=0,
            ),
            char,
            self.engine,
            rng=SequenceRng([4, 18]),
        )
        self.assertEqual(result.mode, "avantage")


class TestGnome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_gnome_cunning_magic_save(self):
        char = finalize_new_character(
            name="Gizmo",
            race_id="gnome",
            class_id="wizard",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(int=15, con=14),
            engine=self.engine,
            skills=["arcana", "history"],
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(sheet.speed, 25)
        result = roll_d20_for_character(
            D20RollRequest(
                roll_type="saving_throw",
                save_versus_condition="magic",
                ability="int",
                ability_modifier=2,
            ),
            char,
            self.engine,
            rng=SequenceRng([5, 16]),
        )
        self.assertEqual(result.mode, "avantage")


class TestHalfOrc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_menacing_intimidation(self):
        char = finalize_new_character(
            name="Grok",
            race_id="half_orc",
            class_id="wizard",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(str=15, con=14),
            engine=self.engine,
            skills=["arcana", "history"],
        )
        sheet = build_character_sheet(char, self.engine)
        labels = " ".join(sheet.proficient_skill_labels)
        self.assertIn("Intimidation", labels)
        self.assertTrue(relentless_endurance_available(char))


class TestTiefling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_fire_resistance_and_innate_spells(self):
        char = finalize_new_character(
            name="Zarath",
            race_id="tiefling",
            class_id="wizard",
            owner_id="1",
            guild_id="1",
            base_scores=valid_point_buy_scores(cha=15, int=14),
            engine=self.engine,
            skills=["arcana", "history"],
        )
        self.assertEqual(get_damage_resistances(char), ("fire",))
        self.assertIn("innate_spells", char.choices)
        sheet = build_character_sheet(char, self.engine)
        self.assertIn("Thaumaturgie", sheet.innate_spells_text)
        self.assertIn("feu", sheet.damage_resistances)


class TestRaceCreationService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Path(self.tmp.name) / "bot.db"
        init_database(db)
        self.service = CharacterService(
            SqliteCharacterRepository(db), self.engine
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_human_still_works(self):
        char = self.service.create_from_wizard(
            owner_id="1",
            guild_id="100",
            name="Human",
            race_id="human",
            class_id="wizard",
            base_scores=valid_point_buy_scores(int=15, con=14),
            skills=list(wizard_creation_kwargs()["skills"]),
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(sheet.race_id, "human")


if __name__ == "__main__":
    unittest.main(verbosity=2)
