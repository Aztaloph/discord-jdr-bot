# tests/unit/test_p1_fix_scorching_ray.py
"""P1-fix — scorching_ray catalogue + ensorceleur niv. 3 + legacy magicien."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import apply_level_up
from jdr_engine.rules.spellcasting.autocomplete_availability import (
    list_autocomplete_spell_ids,
)
from jdr_engine.rules.spellcasting.pools import spell_id_in_class_pool
from jdr_engine.rules.spellcasting.state import (
    get_spellbook,
    get_spells_known,
    list_spell_autocomplete_ids,
)
from tests.helpers.creation import sorcerer_creation_kwargs


class TestScorchingRayFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_scorching_ray_in_compendium_and_class_pools(self):
        entry = self.engine.get_entity("spell", "scorching_ray")
        self.assertIsNotNone(entry)
        self.assertTrue(spell_id_in_class_pool("wizard", "scorching_ray"))
        self.assertTrue(spell_id_in_class_pool("sorcerer", "scorching_ray"))

    def test_sorcerer_level_3_knows_scorching_ray(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Kael",
            engine=self.engine,
            **sorcerer_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        char, _ = apply_level_up(
            char, self.engine, metamagic_options=["quickened", "extended"]
        )
        self.assertIn("scorching_ray", get_spells_known(char))
        self.assertIn("scorching_ray", list_spell_autocomplete_ids(char))

    def test_legacy_wizard_spellbook_fallback_from_prepared(self):
        fixture = Path("fixtures/characters/joe_le_mage.v2.json")
        if not fixture.is_file():
            raise unittest.SkipTest("fixture joe absent")
        data = json.loads(fixture.read_text(encoding="utf-8"))
        raw = data["characters"]["joe00001"]
        char = Character(
            id=raw["id"],
            owner_id=raw["owner_id"],
            guild_id="1",
            name=raw["name"],
            race_id=raw["race_id"],
            class_id=raw["class_id"],
            level=raw["level"],
            ability_scores=raw["ability_scores"],
            choices=raw["choices"],
        )
        self.assertIn("scorching_ray", get_spellbook(char))
        self.assertIn("scorching_ray", list_autocomplete_spell_ids(char, engine=self.engine))


if __name__ == "__main__":
    unittest.main(verbosity=2)
