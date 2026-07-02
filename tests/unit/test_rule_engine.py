# tests/unit/test_rule_engine.py
import unittest

from jdr_engine.rules import RuleEngine
from jdr_engine.compendium.paths import get_ruleset_path


class TestRuleEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_list_races(self):
        races = self.engine.list_entities("race")
        self.assertEqual(len(races), 4)
        ids = {r.entry_id for r in races}
        self.assertIn("elf", ids)

    def test_list_races_plural_alias(self):
        races = self.engine.list_entities("races")
        self.assertEqual(len(races), 4)

    def test_get_elf(self):
        elf = self.engine.get_entity("race", "elf")
        self.assertIsNotNone(elf)
        self.assertEqual(elf.entry_id, "elf")
        self.assertEqual(elf.definition.mechanics["speed"], 30)

    def test_elf_ability_bonuses(self):
        bonuses = self.engine.get_ability_bonuses("elf")
        self.assertEqual(bonuses.get("dex"), 2)

    def test_elf_traits_resolved(self):
        traits = self.engine.get_race_traits("elf")
        trait_ids = {t.entry_id for t in traits}
        self.assertEqual(
            trait_ids,
            {"darkvision", "keen_senses", "fey_ancestry", "trance"},
        )

    def test_fighter_hit_die(self):
        self.assertEqual(self.engine.get_class_hit_die("fighter"), "d10")

    def test_wizard_hit_die(self):
        self.assertEqual(self.engine.get_class_hit_die("wizard"), "d6")

    def test_proficiency_bonus_level_1(self):
        self.assertEqual(self.engine.get_proficiency_bonus(1), 2)

    def test_proficiency_bonus_level_5(self):
        self.assertEqual(self.engine.get_proficiency_bonus(5), 3)

    def test_display_name_fr(self):
        name = self.engine.get_display_name("race", "elf", locale="fr")
        self.assertEqual(name, "Elfe")

    def test_display_name_en(self):
        name = self.engine.get_display_name("race", "elf", locale="en")
        self.assertEqual(name, "Elf")

    def test_presenter_lore_fr(self):
        lore = self.engine.presenter.get_lore("race", "elf", locale="fr")
        self.assertIsNotNone(lore)
        self.assertIn("magique", lore.lower())

    def test_presenter_lore_en(self):
        lore = self.engine.presenter.get_lore("race", "elf", locale="en")
        self.assertIsNotNone(lore)
        self.assertIn("magical", lore.lower())

    def test_entity_exists(self):
        self.assertTrue(self.engine.entity_exists("race", "orc") is False)
        self.assertTrue(self.engine.entity_exists("race", "elf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
