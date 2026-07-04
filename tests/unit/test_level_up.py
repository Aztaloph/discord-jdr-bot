# tests/unit/test_level_up.py
"""Montée de niveau Lot 2 — Magicien & Clerc, niv. 2–3."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import CharacterService
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_progression import LevelUpError, apply_level_up
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
from jdr_engine.rules.spellcasting.state import format_slots_display

from tests.helpers.creation import cleric_creation_kwargs, wizard_creation_kwargs


class TestLevelUpEngine(unittest.TestCase):
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
        self.guild_id = "900"

    def tearDown(self):
        self.tmp.cleanup()

    def _wizard(self, name: str = "Merlin"):
        return self.service.create_from_wizard(
            owner_id="1",
            guild_id=self.guild_id,
            name=name,
            **wizard_creation_kwargs(),
        )

    def _cleric(self, name: str = "Clerc"):
        return self.service.create_from_wizard(
            owner_id="1",
            guild_id=self.guild_id,
            name=name,
            **cleric_creation_kwargs(),
        )

    def test_wizard_level_1_to_2_hp_and_slots(self):
        char = self._wizard()
        sheet1 = build_character_sheet(char, self.engine)
        self.assertEqual(char.level, 1)
        self.assertEqual(sheet1.hp_max, 8)  # d6 + CON 14 (+2)
        self.assertEqual(get_max_spell_slots("wizard", 1), {1: 2})

        updated, result = apply_level_up(char, self.engine)
        self.assertEqual(result.old_level, 1)
        self.assertEqual(result.new_level, 2)
        self.assertEqual(result.hp_gain, 6)  # 3+1+2
        self.assertEqual(result.hp_max_after, 14)
        self.assertEqual(result.slots_max_before, "niv.1: 2")
        self.assertEqual(result.slots_max_after, "niv.1: 3")
        self.assertEqual(updated.level, 2)
        self.assertEqual(get_max_spell_slots("wizard", 2), {1: 3})

    def test_wizard_level_2_to_3_hp_and_slots(self):
        char = self._wizard()
        char, _ = apply_level_up(char, self.engine)
        char, result = apply_level_up(char, self.engine)
        self.assertEqual(result.new_level, 3)
        self.assertEqual(result.hp_max_after, 20)
        self.assertEqual(result.slots_max_after, "niv.1: 4, niv.2: 2")
        self.assertEqual(get_max_spell_slots("wizard", 3), {1: 4, 2: 2})

    def test_cleric_level_1_to_3(self):
        char = self._cleric()
        sheet1 = build_character_sheet(char, self.engine)
        self.assertEqual(sheet1.hp_max, 10)  # d8 + CON 14 (+2)

        char, r1 = apply_level_up(char, self.engine)
        self.assertEqual(r1.hp_gain, 7)  # 4+1+2
        self.assertEqual(r1.hp_max_after, 17)
        self.assertEqual(r1.slots_max_after, "niv.1: 3")

        char, r2 = apply_level_up(char, self.engine)
        self.assertEqual(r2.new_level, 3)
        self.assertEqual(r2.hp_max_after, 24)
        self.assertEqual(r2.slots_max_after, "niv.1: 4, niv.2: 2")

    def test_hit_dice_increment(self):
        char = self._wizard()
        char, r1 = apply_level_up(char, self.engine)
        self.assertEqual(r1.hit_dice_after, 2)
        char, r2 = apply_level_up(char, self.engine)
        self.assertEqual(r2.hit_dice_after, 3)

    def test_level_3_cannot_level_up_again(self):
        char = self._wizard()
        char, _ = apply_level_up(char, self.engine)
        char, _ = apply_level_up(char, self.engine)
        with self.assertRaises(LevelUpError):
            apply_level_up(char, self.engine)

    def test_persisted_and_sheet_reflect_level_up(self):
        char = self._wizard()
        self.service.save(char)
        result = self.service.level_up_on_guild(char.id, self.guild_id)
        self.assertEqual(result.new_level, 2)

        reloaded = self.service.get_on_guild(char.id, self.guild_id)
        sheet = build_character_sheet(reloaded, self.engine)
        self.assertEqual(reloaded.level, 2)
        self.assertEqual(sheet.level, 2)
        self.assertEqual(sheet.hp_max, 14)
        self.assertIn("niv.1: 3", format_slots_display(reloaded))

    def test_proficiency_unchanged_at_level_2(self):
        char = self._wizard()
        sheet1 = build_character_sheet(char, self.engine)
        char, _ = apply_level_up(char, self.engine)
        sheet2 = build_character_sheet(char, self.engine)
        self.assertEqual(sheet1.proficiency_bonus, 2)
        self.assertEqual(sheet2.proficiency_bonus, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
