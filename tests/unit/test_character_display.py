# tests/unit/test_character_display.py
import unittest

from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.domain.character.character_sheet import CharacterSheet
from jdr_engine.rules import RuleEngine

from interfaces.discord.formatters.character_embed import build_character_display


def _sample_sheet(**overrides) -> CharacterSheet:
    defaults = dict(
        character_id="abc12345",
        name="Doudou",
        owner_id="1",
        ruleset_id="dnd5e",
        race_id="halfling",
        race_name="Halfelin",
        class_id="ranger",
        class_name="Rôdeur",
        level=1,
        ability_scores_base={"str": 10, "dex": 12, "con": 10, "int": 10, "wis": 10, "cha": 10},
        ability_scores={"str": 10, "dex": 12, "con": 10, "int": 10, "wis": 10, "cha": 10},
        ability_modifiers={"str": 0, "dex": 1, "con": 0, "int": 0, "wis": 0, "cha": 0},
        proficiency_bonus=2,
        hit_die="d8",
        hp_max=8,
        hp_current=8,
        ac=11,
        speed=25,
    )
    defaults.update(overrides)
    return CharacterSheet(**defaults)


class TestCharacterDisplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_halfling_lore_in_description(self):
        display = build_character_display(
            _sample_sheet(), self.engine, locale="fr"
        )
        self.assertIsNotNone(display.embed.description)
        self.assertIn("halfelin", display.embed.description.lower())

    def test_no_lore_without_engine(self):
        display = build_character_display(_sample_sheet(), None)
        self.assertIsNone(display.embed.description)

    def test_traits_and_attacks_both_present(self):
        display = build_character_display(
            _sample_sheet(
                trait_ids=["darkvision"],
                trait_names=["Vision dans le noir"],
            ),
            self.engine,
        )
        field_names = [f.name for f in display.embed.fields]
        self.assertIn("✨ Traits raciaux", field_names)
        self.assertIn("⚔️ Attaques", field_names)


if __name__ == "__main__":
    unittest.main()
