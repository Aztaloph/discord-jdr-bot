# tests/unit/test_p2g_mj_grimoire_reset.py
"""P2g — réinitialisation grimoire mage (service + règles, sans Discord)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import (
    CharacterNotFoundError,
    CharacterService,
    CharacterValidationError,
)
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.model import wizard_prepared_capacity
from jdr_engine.rules.spellcasting.preparation import (
    WizardSpellbookResetError,
    is_wizard_spellcasting_canonical,
    project_wizard_spellcasting_reset,
    rebuild_wizard_spellcasting_at_level,
)
from jdr_engine.rules.spellcasting.spells_catalog import WIZARD_SPELLBOOK_POOL
from jdr_engine.rules.spellcasting.prepared_choice import is_prepared_rechoice_pending
from jdr_engine.rules.spellcasting.state import (
    get_cantrips_known,
    get_spellbook,
    get_slots_used,
    get_spells_prepared_list,
)
from tests.helpers.creation import cleric_creation_kwargs, wizard_creation_kwargs


def _polluted_preview_result(*, character_id: str = "joe00001") -> "WizardGrimoireResetResult":
    """DTO preview identique à ce que construit ``mj_reset_grimoire`` sur perso pollué."""
    from jdr_engine.application.dto.wizard_grimoire_reset import WizardGrimoireResetResult
    from jdr_engine.rules.spellcasting.preparation import project_wizard_spellcasting_reset
    from jdr_engine.rules.spellcasting.state import (
        get_cantrips_known,
        get_spellbook,
        get_spells_prepared_list,
    )

    char = _polluted_wizard_level1()
    char.id = character_id
    projected = project_wizard_spellcasting_reset(char)
    return WizardGrimoireResetResult(
        character_id=char.id,
        character_name=char.name,
        already_clean=False,
        cantrips_before=tuple(get_cantrips_known(char)),
        cantrips_after=tuple(get_cantrips_known(projected)),
        spellbook_before=tuple(get_spellbook(char)),
        spellbook_after=tuple(get_spellbook(projected)),
        prepared_before=tuple(get_spells_prepared_list(char)),
        prepared_after=tuple(get_spells_prepared_list(projected)),
    )


def _polluted_wizard_level1(*, int_score: int = 15) -> Character:
    """Perso legacy : grimoire pollué + ``bless`` préparé hors nouveau canon."""
    canonical_book = list(WIZARD_SPELLBOOK_POOL[:6])
    polluted_book = canonical_book + ["bless", "inflict_wounds"]
    return Character(
        owner_id="1",
        name="Joe le mage",
        race_id="human",
        class_id="wizard",
        level=1,
        ability_scores=AbilityScores(
            scores={
                "str": 8,
                "dex": 8,
                "con": 14,
                "int": int_score,
                "wis": 8,
                "cha": 8,
            }
        ),
        choices={
            "spellcasting": {
                "cantrips_known": ["fire_bolt", "thaumaturgy", "guidance"],
                "spellbook": polluted_book,
                "spells_prepared": ["bless", "magic_missile", "shield"],
                "slots_used": {1: 1},
                "prepared_rechoice_pending": True,
            }
        },
    )


class TestP2gWizardGrimoireResetRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_rebuild_non_wizard_raises(self):
        char = Character(
            owner_id="1",
            name="Clerc",
            race_id="human",
            class_id="cleric",
            level=1,
            ability_scores=AbilityScores(scores=dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)),
            choices={"spellcasting": {"cantrips_known": [], "spells_prepared": [], "slots_used": {}}},
        )
        with self.assertRaises(WizardSpellbookResetError):
            rebuild_wizard_spellcasting_at_level(char)

    def test_fresh_wizard_is_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            init_database(db)
            service = CharacterService(SqliteCharacterRepository(db), self.engine)
            char = service.create_from_wizard(
                owner_id="1",
                guild_id="100",
                name="Canon",
                **wizard_creation_kwargs(),
            )
            self.assertTrue(is_wizard_spellcasting_canonical(char))

    def test_polluted_spellbook_not_canonical(self):
        char = _polluted_wizard_level1()
        self.assertFalse(is_wizard_spellcasting_canonical(char))

    def test_project_removes_polluted_spellbook_entries(self):
        char = _polluted_wizard_level1()
        projected = project_wizard_spellcasting_reset(char)
        book = get_spellbook(projected)
        self.assertNotIn("bless", book)
        self.assertNotIn("inflict_wounds", book)
        self.assertEqual(book, list(WIZARD_SPELLBOOK_POOL[:6]))

    def test_polluted_prepared_bless_removed_and_quota_rebalanced(self):
        char = _polluted_wizard_level1()
        int_mod = 2
        capacity = wizard_prepared_capacity(int_mod, char.level)

        projected = project_wizard_spellcasting_reset(char)
        prepared = get_spells_prepared_list(projected)
        spellbook = set(get_spellbook(projected))

        self.assertNotIn("bless", prepared)
        self.assertEqual(len(prepared), capacity)
        self.assertTrue(all(spell in spellbook for spell in prepared))

    def test_rebuild_preserves_slots_used_and_rechoice_flag(self):
        char = _polluted_wizard_level1()
        updated = rebuild_wizard_spellcasting_at_level(char)
        self.assertEqual(get_slots_used(updated), {1: 1})
        self.assertTrue(is_prepared_rechoice_pending(updated))

    def test_rebuild_normalizes_cantrips(self):
        char = _polluted_wizard_level1()
        char.choices["spellcasting"]["cantrips_known"] = ["fire_bolt"]
        updated = rebuild_wizard_spellcasting_at_level(char)
        self.assertEqual(get_cantrips_known(updated), ["fire_bolt", "thaumaturgy", "guidance"])


class TestP2gWizardGrimoireResetService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def _service(self, db_path: Path) -> CharacterService:
        init_database(db_path)
        return CharacterService(SqliteCharacterRepository(db_path), self.engine)

    def test_service_reset_persists_canonical_grimoire(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            char = service.create_from_wizard(
                owner_id="1",
                guild_id="555",
                name="Joe",
                **wizard_creation_kwargs(),
            )
            char.choices = dict(char.choices or {})
            char.choices["spellcasting"] = _polluted_wizard_level1().choices["spellcasting"]
            service.save(char)

            result = service.reset_wizard_grimoire_on_guild(char.id, "555")
            self.assertFalse(result.already_clean)
            self.assertIn("bless", result.removed_from_spellbook)
            self.assertIn("bless", result.removed_from_prepared)
            self.assertNotIn("bless", result.prepared_after)

            reloaded = service.get_on_guild(char.id, "555")
            self.assertEqual(get_spellbook(reloaded), list(result.spellbook_after))
            self.assertEqual(get_spells_prepared_list(reloaded), list(result.prepared_after))
            self.assertEqual(get_slots_used(reloaded), {1: 1})

    def test_service_already_clean_skips_second_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            char = service.create_from_wizard(
                owner_id="1",
                guild_id="555",
                name="Clean",
                **wizard_creation_kwargs(),
            )
            first = service.reset_wizard_grimoire_on_guild(char.id, "555")
            self.assertTrue(first.already_clean)
            second = service.reset_wizard_grimoire_on_guild(char.id, "555")
            self.assertTrue(second.already_clean)

    def test_service_non_wizard_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            char = service.create_from_wizard(
                owner_id="1",
                guild_id="555",
                name="Clerc",
                **cleric_creation_kwargs(),
            )
            with self.assertRaises(CharacterValidationError):
                service.reset_wizard_grimoire_on_guild(char.id, "555")

    def test_service_unknown_character_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = self._service(db)
            with self.assertRaises(CharacterNotFoundError):
                service.reset_wizard_grimoire_on_guild("inconnu01", "555")


class TestP2gGrimoireResetEmbeds(unittest.TestCase):
    """Contenu des embeds Discord (preview + succès) — sans interaction boutons."""

    def test_confirm_embed_shows_before_after_on_polluted_wizard(self):
        from interfaces.discord.handlers.mj_grimoire import build_grimoire_reset_confirm_embed

        preview = _polluted_preview_result()
        embed = build_grimoire_reset_confirm_embed(preview)
        desc = embed.description or ""

        self.assertEqual(embed.title, "⚠️ Confirmation requise (MJ)")
        self.assertIn("Joe le mage", desc)
        self.assertIn("joe00001", desc)
        self.assertIn("`bless`", desc)
        self.assertIn("`inflict_wounds`", desc)
        self.assertNotIn("Retirés du grimoire", desc)
        self.assertIn(
            "**Grimoire actuel** : `chromatic_orb`, `burning_hands`, `detect_magic`, "
            "`magic_missile`, `shield`, `scorching_ray`, `bless`, `inflict_wounds`",
            desc,
        )
        self.assertIn(
            "**Grimoire après** : `chromatic_orb`, `burning_hands`, `detect_magic`, "
            "`magic_missile`, `shield`, `scorching_ray`",
            desc,
        )
        self.assertIn("**Préparés actuels** : `bless`, `magic_missile`, `shield`", desc)
        self.assertIn(
            "**Préparés après** : `magic_missile`, `shield`, `chromatic_orb`",
            desc,
        )

    def test_success_embed_lists_removed_intruders_on_polluted_wizard(self):
        from interfaces.discord.handlers.mj_grimoire import build_grimoire_reset_embed

        preview = _polluted_preview_result()
        embed = build_grimoire_reset_embed(preview)
        desc = embed.description or ""

        self.assertEqual(embed.title, "✅ Grimoire réinitialisé")
        self.assertIn("→", desc)
        self.assertIn("**Retirés du grimoire** : `bless`, `inflict_wounds`", desc)
        self.assertIn("**Retirés des préparés** : `bless`", desc)
        self.assertIn("**Préparés** : `bless`, `magic_missile`, `shield`", desc)
        self.assertIn("→ `magic_missile`, `shield`, `chromatic_orb`", desc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
