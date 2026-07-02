# tests/unit/test_character_calculator.py
import unittest

from jdr_engine.domain.character import AbilityScores, Character
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import (
    ability_modifier,
    apply_racial_bonuses,
    build_character_sheet,
    parse_hit_die,
)


class TestCalculator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_ability_modifier(self):
        self.assertEqual(ability_modifier(10), 0)
        self.assertEqual(ability_modifier(15), 2)
        self.assertEqual(ability_modifier(8), -1)

    def test_parse_hit_die(self):
        self.assertEqual(parse_hit_die("d10"), 10)

    def test_apply_racial_bonuses(self):
        base = {"str": 10, "dex": 10, "con": 10}
        result = apply_racial_bonuses(base, {"dex": 2})
        self.assertEqual(result["dex"], 12)

    def test_fighter_level_1_sheet(self):
        char = Character(
            owner_id="1",
            name="Test",
            race_id="human",
            class_id="fighter",
            level=1,
            ability_scores=AbilityScores.from_dict(
                {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}
            ),
        )
        sheet = build_character_sheet(char, self.engine, locale="fr")
        self.assertEqual(sheet.hit_die, "d10")
        self.assertEqual(sheet.proficiency_bonus, 2)
        self.assertEqual(sheet.hp_max, 12)  # d10 + CON eff. 14 (+2), humain +1 CON
        self.assertEqual(sheet.race_name, "Humain")

    def test_elf_dex_bonus_in_sheet(self):
        char = Character(
            owner_id="1",
            name="Elfy",
            race_id="elf",
            class_id="fighter",
            level=1,
            ability_scores=AbilityScores.from_dict(
                dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)
            ),
        )
        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(sheet.ability_scores["dex"], 12)
        self.assertEqual(len(sheet.trait_ids), 4)

    def test_halfling_ranger_level_1_dex_and_hp(self):
        """Halfelin + Rôdeur niv.1, base DEX/CON 10 → DEX 12, PV 10 (d10)."""
        char = Character(
            owner_id="1",
            name="Doudou",
            race_id="halfling",
            class_id="ranger",
            level=1,
            ability_scores=AbilityScores.from_dict(
                dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)
            ),
        )
        sheet = build_character_sheet(char, self.engine, locale="fr")
        self.assertEqual(sheet.ability_scores_base["dex"], 10)
        self.assertEqual(sheet.ability_scores["dex"], 12)
        self.assertEqual(sheet.ability_modifiers["dex"], 1)
        self.assertEqual(sheet.hit_die, "d10")
        self.assertEqual(sheet.hp_max, 10)
        self.assertEqual(sheet.class_name, "Rôdeur")

    def test_rogue_level_1_hp_d8(self):
        """Roublard niv.1 CON 10 → PV 8 (d8), distinct du Rôdeur d10."""
        char = Character(
            owner_id="1",
            name="Voleur",
            race_id="human",
            class_id="rogue",
            level=1,
            ability_scores=AbilityScores.from_dict(
                dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)
            ),
        )
        sheet = build_character_sheet(char, self.engine, locale="fr")
        self.assertEqual(sheet.hit_die, "d8")
        self.assertEqual(sheet.hp_max, 8)
        self.assertEqual(sheet.class_name, "Roublard")


if __name__ == "__main__":
    unittest.main(verbosity=2)
