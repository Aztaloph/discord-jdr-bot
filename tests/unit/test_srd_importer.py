# tests/unit/test_srd_importer.py
"""Tests mapping SRD 2014 → mechanics (sans écriture disque)."""
import unittest

from jdr_engine.compendium.srd_importer import (
    map_class_mechanics,
    map_race_mechanics,
    merge_mechanics_preserve_existing,
    preserve_todo_comments,
)


class TestSrdImporterMapping(unittest.TestCase):
    def test_map_halfling_mechanics(self):
        srd = {
            "index": "halfling",
            "name": "Halfling",
            "speed": 25,
            "size": "Small",
            "ability_bonuses": [
                {
                    "ability_score": {"index": "dex", "name": "DEX"},
                    "bonus": 2,
                }
            ],
            "languages": [{"index": "common"}, {"index": "halfling"}],
            "age": "ignored",
            "alignment": "ignored",
            "size_description": "ignored",
        }
        mechanics = map_race_mechanics(srd)
        self.assertEqual(mechanics["size"], "small")
        self.assertEqual(mechanics["speed"], 25)
        self.assertEqual(mechanics["ability_score_increase"], [{"ability": "dex", "value": 2}])
        self.assertEqual(mechanics["languages"]["fixed"], ["common", "halfling"])
        self.assertEqual(mechanics["traits"], [])

    def test_map_ranger_mechanics(self):
        srd = {
            "index": "ranger",
            "name": "Ranger",
            "hit_die": 10,
            "saving_throws": [{"index": "str"}, {"index": "dex"}],
            "proficiencies": [
                {"index": "light-armor"},
                {"index": "medium-armor"},
                {"index": "shields"},
                {"index": "simple-weapons"},
                {"index": "martial-weapons"},
            ],
            "proficiency_choices": [
                {
                    "choose": 3,
                    "type": "proficiencies",
                    "from": {
                        "options": [
                            {"item": {"index": "skill-stealth"}},
                            {"item": {"index": "skill-survival"}},
                        ]
                    },
                }
            ],
            "spellcasting": {
                "level": 2,
                "spellcasting_ability": {"index": "wis"},
                "info": [{"name": "ignored", "desc": ["must not import"]}],
            },
            "url": "/api/2014/classes/ranger",
        }
        mechanics = map_class_mechanics(srd)
        self.assertEqual(mechanics["hit_die"], "d10")
        self.assertEqual(mechanics["saving_throw_proficiencies"], ["str", "dex"])
        self.assertIn("light", mechanics["armor_proficiencies"])
        self.assertIn("martial", mechanics["weapon_proficiencies"])
        self.assertEqual(mechanics["skill_choices"]["count"], 3)
        self.assertIn("stealth", mechanics["skill_choices"]["from"])
        self.assertEqual(mechanics["spellcasting"], {"level": 2, "ability": "wis"})
        self.assertNotIn("info", mechanics.get("spellcasting", {}))

    def test_map_rogue_hit_die_d8(self):
        srd = {
            "index": "rogue",
            "hit_die": 8,
            "saving_throws": [{"index": "dex"}, {"index": "int"}],
            "proficiencies": [{"index": "light-armor"}, {"index": "simple-weapons"}],
            "proficiency_choices": [],
        }
        mechanics = map_class_mechanics(srd)
        self.assertEqual(mechanics["hit_die"], "d8")

    def test_merge_preserves_traits_and_language_choose(self):
        existing = {
            "traits": [{"ref": "traits/darkvision"}],
            "languages": {
                "fixed": ["common"],
                "choose": {"count": 1, "from": ["elvish"]},
            },
            "speed": 30,
        }
        incoming = {
            "traits": [],
            "languages": {"fixed": ["common"]},
            "speed": 30,
        }
        merged = merge_mechanics_preserve_existing(existing, incoming)
        self.assertEqual(merged["traits"], existing["traits"])
        self.assertEqual(merged["languages"]["choose"], existing["languages"]["choose"])

    def test_preserve_todo_comments_inline_and_block(self):
        original = (
            "mechanics:\n"
            "  traits: []  # TODO Phase 4.5: traits halfelin\n"
            "  features_by_level:\n"
            "    # TODO Phase 4.5: features ranger\n"
            '    "1": [a]\n'
        )
        new = "mechanics:\n  traits: []\n  features_by_level:\n    \"1\": [a]\n"
        restored = preserve_todo_comments(original, new)
        self.assertIn("# TODO Phase 4.5: traits halfelin", restored)
        self.assertIn("# TODO Phase 4.5: features ranger", restored)


if __name__ == "__main__":
    unittest.main()
