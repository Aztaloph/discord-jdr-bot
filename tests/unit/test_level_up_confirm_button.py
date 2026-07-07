# tests/unit/test_level_up_confirm_button.py
"""Bouton Confirmer — montée de niveau multi-select (métamagie, barde)."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import LevelUpPending, LevelUpPendingChoice, apply_level_up

from interfaces.discord.views.level_up_choice import LevelUpChoiceView, LevelUpMultiConfirmButton
from tests.helpers.creation import bard_creation_kwargs, sorcerer_creation_kwargs


class TestLevelUpConfirmButtonState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _metamagic_pending(self) -> LevelUpPending:
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

    def test_confirm_button_disabled_without_selection(self):
        pending = self._metamagic_pending()
        view = LevelUpChoiceView(
            pending,
            self.engine,
            MagicMock(),
            "900",
            "char-id",
        )
        confirm = next(c for c in view.children if isinstance(c, LevelUpMultiConfirmButton))
        self.assertTrue(confirm.disabled)

    def test_confirm_button_enabled_with_two_metamagic(self):
        pending = self._metamagic_pending()
        view = LevelUpChoiceView(
            pending,
            self.engine,
            MagicMock(),
            "900",
            "char-id",
            selected_values=["extended", "subtle"],
        )
        confirm = next(c for c in view.children if isinstance(c, LevelUpMultiConfirmButton))
        self.assertFalse(confirm.disabled)
        self.assertEqual(view.selected_values, ["extended", "subtle"])

    def test_bard_expertise_confirm_enabled_after_lore_skills(self):
        from dataclasses import replace

        char = finalize_new_character(
            owner_id="1",
            guild_id="900",
            name="Melody",
            engine=self.engine,
            **bard_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        with self.assertRaises(LevelUpPendingChoice):
            apply_level_up(char, self.engine)
        with self.assertRaises(LevelUpPendingChoice) as ctx_lore:
            apply_level_up(char, self.engine, subclass="lore")
        merged = replace(
            char,
            choices={
                **(char.choices or {}),
                **(ctx_lore.exception.pending.character.choices or {}),
            },
        )
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(
                merged,
                self.engine,
                subclass="lore",
                lore_bonus_skills=["arcana", "history", "investigation"],
            )
        pending = ctx.exception.pending
        self.assertEqual(pending.choice_type, "expertise_skills")
        skills = list(merged.choices.get("skills", []))
        view = LevelUpChoiceView(
            pending,
            self.engine,
            MagicMock(),
            "900",
            merged.id,
            selected_values=skills[:2],
        )
        confirm = next(c for c in view.children if isinstance(c, LevelUpMultiConfirmButton))
        self.assertFalse(confirm.disabled)


if __name__ == "__main__":
    unittest.main(verbosity=2)
