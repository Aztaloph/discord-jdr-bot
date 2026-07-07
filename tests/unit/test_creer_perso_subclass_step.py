# tests/unit/test_creer_perso_subclass_step.py
"""Création /creer-perso — étape sous-classe niv. 1 (Occultiste et générique)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.class_choices import (
    get_creation_subclass_options,
    requires_subclass_choice_step_at_creation,
)
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import apply_level_up
from interfaces.discord.views.creer_perso_wizard import CreerPersoWizard
from tests.helpers.creation import warlock_creation_kwargs, wizard_creation_kwargs


class TestCreerPersoSubclassStep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_warlock_requires_generic_subclass_step(self):
        self.assertTrue(
            requires_subclass_choice_step_at_creation(self.engine, "warlock")
        )
        options = get_creation_subclass_options(self.engine, "warlock")
        self.assertEqual(tuple(o[0] for o in options), ("fiend",))

    def test_wizard_and_cleric_no_generic_subclass_step(self):
        self.assertFalse(
            requires_subclass_choice_step_at_creation(self.engine, "wizard")
        )
        self.assertFalse(
            requires_subclass_choice_step_at_creation(self.engine, "cleric")
        )
        self.assertFalse(
            requires_subclass_choice_step_at_creation(self.engine, "sorcerer")
        )

    def test_wizard_routes_to_finalize_after_skills(self):
        from jdr_engine.application.character_service import CharacterService
        from jdr_engine.persistence.database import init_database
        from jdr_engine.persistence.sqlite_character_repository import (
            SqliteCharacterRepository,
        )
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            init_database(db)
            service = CharacterService(SqliteCharacterRepository(db), self.engine)
            wizard = CreerPersoWizard(
                character_service=service,
                engine=self.engine,
                state=__import__(
                    "interfaces.discord.views.creer_perso_wizard", fromlist=["CreerPersoState"]
                ).CreerPersoState(
                    owner_id=1,
                    guild_id="100",
                    name="Merlin",
                    class_id="wizard",
                    race_id="human",
                ),
            )
            self.assertEqual(wizard.next_step_after_skills(), "finalize")

    def test_warlock_routes_to_subclass_choice_after_skills(self):
        from jdr_engine.application.character_service import CharacterService
        from jdr_engine.persistence.database import init_database
        from jdr_engine.persistence.sqlite_character_repository import (
            SqliteCharacterRepository,
        )
        import tempfile
        from interfaces.discord.views.creer_perso_wizard import CreerPersoState

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            init_database(db)
            service = CharacterService(SqliteCharacterRepository(db), self.engine)
            wizard = CreerPersoWizard(
                character_service=service,
                engine=self.engine,
                state=CreerPersoState(
                    owner_id=1,
                    guild_id="100",
                    name="Morrigan",
                    class_id="warlock",
                    race_id="human",
                ),
            )
            self.assertEqual(wizard.next_step_after_skills(), "subclass_choice")

    def test_finalize_warlock_without_patron_fails(self):
        scores = dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 8)
        scores["cha"] = 15
        with self.assertRaises(ValueError) as ctx:
            finalize_new_character(
                owner_id="1",
                guild_id="1",
                name="Morrigan",
                engine=self.engine,
                race_id="human",
                class_id="warlock",
                base_scores=scores,
                skills=["arcana", "deception"],
            )
        self.assertIn("fiend", str(ctx.exception).lower())

    def test_finalize_warlock_with_patron_fiend(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=1),
        )
        self.assertEqual(char.choices.get("specialization"), "fiend")
        self.assertIn("eldritch_blast", char.choices["spellcasting"]["cantrips_known"])

    def test_warlock_patron_persists_after_level_up(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(
            char,
            self.engine,
            eldritch_invocations=["agonizing_blast", "devils_sight"],
        )
        char, r3 = apply_level_up(
            char,
            self.engine,
            eldritch_invocations=["agonizing_blast", "devils_sight"],
            pact_boon="pact_of_the_chain",
        )
        self.assertEqual(r3.new_level, 3)
        self.assertEqual(char.choices.get("specialization"), "fiend")

    def test_wizard_creation_unchanged(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        self.assertNotIn("specialization", char.choices or {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
