# tests/unit/test_p1_fix_metamagic.py
"""P1-fix — confirmation métamagie ensorceleur niv. 3 (montée de niveau)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from jdr_engine.application.character_service import CharacterService
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import LevelUpPendingChoice, apply_level_up

from interfaces.discord.views.level_up_choice import (
    LevelUpChoiceView,
    LevelUpMultiConfirmButton,
    LevelUpMultiSelect,
)
from tests.helpers.creation import sorcerer_creation_kwargs


class TestMetamagicConfirmFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _metamagic_pending(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="900",
            name="Kael",
            engine=self.engine,
            **sorcerer_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        return ctx.exception.pending

    def test_metamagic_multiselect_requires_exact_pick_count(self):
        pending = self._metamagic_pending()
        view = LevelUpChoiceView(
            pending,
            self.engine,
            MagicMock(),
            "900",
            "char-id",
        )
        multi = next(c for c in view.children if isinstance(c, LevelUpMultiSelect))
        self.assertEqual(multi.min_values, pending.required_count)
        self.assertEqual(multi.max_values, pending.required_count)

    def test_metamagic_confirm_persists_via_character_service(self):
        tmp = tempfile.TemporaryDirectory()
        db = Path(tmp.name) / "bot.db"
        init_database(db)
        service = CharacterService(SqliteCharacterRepository(db), self.engine)
        guild_id = "900"

        char = service.create_from_wizard(
            owner_id="1",
            guild_id=guild_id,
            name="Kael",
            **sorcerer_creation_kwargs(level=1),
        )
        service.level_up_on_guild(char.id, guild_id)
        reloaded = service.get_on_guild(char.id, guild_id)
        with self.assertRaises(LevelUpPendingChoice):
            service.level_up_on_guild(reloaded.id, guild_id)

        result = service.complete_level_up_choice_on_guild(
            reloaded.id,
            guild_id,
            metamagic_options=["extended", "subtle"],
            base_character=reloaded,
        )
        final = service.get_on_guild(char.id, guild_id)
        self.assertEqual(result.new_level, 3)
        self.assertEqual(final.choices.get("metamagic_options"), ["extended", "subtle"])
        sheet = build_character_sheet(final, self.engine)
        joined = "\n".join(sheet.class_features_lines).lower()
        self.assertIn("prolongé", joined)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
