# tests/unit/test_p2e_prepared_choice.py
"""P2e — re-préparation sorts clerc / druide / paladin / magicien (repos long)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import apply_level_up
from jdr_engine.rules.rest import apply_long_rest
from jdr_engine.rules.spellcasting.autocomplete_availability import (
    SpellAutocompleteAvailability,
    compute_spell_autocomplete_availability,
)
from jdr_engine.rules.spellcasting.prepared_choice import (
    PreparedChoiceError,
    apply_prepared_selection,
    get_player_prepared_quota,
    get_prepared_spell_pool,
    is_prepared_rechoice_pending,
    mark_prepared_rechoice_pending,
    validate_prepared_selection,
)
from jdr_engine.rules.spellcasting.state import get_domain_spells, get_spells_prepared_list
from tests.helpers.creation import (
    cleric_creation_kwargs,
    druid_creation_kwargs,
    paladin_creation_kwargs,
    ranger_creation_kwargs,
    sorcerer_creation_kwargs,
    valid_point_buy_scores,
)


class TestPreparedChoiceCreationAndLevelUp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_creation_has_prepared_spells_and_no_pending_flag(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Marie",
            engine=self.engine,
            **cleric_creation_kwargs(),
        )
        self.assertGreater(len(get_spells_prepared_list(char)), 0)
        self.assertFalse(is_prepared_rechoice_pending(char))

    def test_level_up_keeps_prepared_and_no_pending(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Fern",
            engine=self.engine,
            **druid_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, subclass="land", subchoice_value="forest")
        self.assertGreater(len(get_spells_prepared_list(char)), 0)
        self.assertFalse(is_prepared_rechoice_pending(char))


class TestPreparedChoiceValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _pending_cleric(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Marie",
            engine=self.engine,
            **cleric_creation_kwargs(),
        )
        char, _ = apply_long_rest(char, self.engine)
        self.assertTrue(is_prepared_rechoice_pending(char))
        return char

    def _pending_druid(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Fern",
            engine=self.engine,
            **druid_creation_kwargs(level=1),
        )
        char, _ = apply_long_rest(char, self.engine)
        self.assertTrue(is_prepared_rechoice_pending(char))
        return char

    def _pending_druid_quota_three(self):
        """Druide SAG base 13 + humain → mod +2, quota 3 (= pool niv. 1)."""
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Fern",
            engine=self.engine,
            **druid_creation_kwargs(
                level=1,
                base_scores=valid_point_buy_scores(wis=13, con=14),
            ),
        )
        char, _ = apply_long_rest(char, self.engine)
        self.assertTrue(is_prepared_rechoice_pending(char))
        return char

    def _pending_cleric_quota_three(self):
        """Clerc SAG base 13 + humain → mod +2, quota 3."""
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Marie",
            engine=self.engine,
            **cleric_creation_kwargs(
                base_scores=valid_point_buy_scores(wis=13, con=14),
            ),
        )
        char, _ = apply_long_rest(char, self.engine)
        self.assertTrue(is_prepared_rechoice_pending(char))
        return char

    def _player_prepared_pool(self, char):
        domain = set(get_domain_spells(char))
        return [
            spell_id
            for spell_id in get_prepared_spell_pool(char, engine=self.engine)
            if spell_id not in domain
        ]

    def test_valid_selection_persisted(self):
        char = self._pending_druid_quota_three()
        quota = get_player_prepared_quota(char, engine=self.engine)
        self.assertEqual(quota, 3)
        pool = list(get_prepared_spell_pool(char, engine=self.engine))
        selection = pool[:quota]
        updated = apply_prepared_selection(
            char, self.engine, selection, require_pending=True
        )
        self.assertEqual(get_spells_prepared_list(updated), selection)
        self.assertFalse(is_prepared_rechoice_pending(updated))

    def test_refuse_spell_outside_pool(self):
        char = self._pending_druid_quota_three()
        quota = get_player_prepared_quota(char, engine=self.engine)
        pool = list(get_prepared_spell_pool(char, engine=self.engine))
        with self.assertRaises(PreparedChoiceError) as ctx:
            validate_prepared_selection(
                char,
                self.engine,
                ["magic_missile", *pool[: quota - 1]],
            )
        self.assertIn("hors liste", str(ctx.exception).lower())

    def test_refuse_cleric_domain_spell_in_selection(self):
        char = self._pending_cleric_quota_three()
        quota = get_player_prepared_quota(char, engine=self.engine)
        self.assertEqual(quota, 3)
        pool = self._player_prepared_pool(char)
        with self.assertRaises(PreparedChoiceError) as ctx:
            validate_prepared_selection(
                char,
                self.engine,
                ["bless", *pool[: quota - 1]],
            )
        self.assertIn("domaine", str(ctx.exception).lower())

    def test_refuse_wrong_quota(self):
        char = self._pending_cleric()
        with self.assertRaises(PreparedChoiceError) as ctx:
            validate_prepared_selection(char, self.engine, ["cure_wounds"])
        self.assertIn("exactement", str(ctx.exception).lower())

    def test_refuse_without_pending_flag(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Marie",
            engine=self.engine,
            **cleric_creation_kwargs(),
        )
        quota = get_player_prepared_quota(char, engine=self.engine)
        with self.assertRaises(PreparedChoiceError) as ctx:
            validate_prepared_selection(
                char,
                self.engine,
                ["cure_wounds", "bless", "detect_magic"][:quota],
            )
        self.assertIn("repos long", str(ctx.exception).lower())

    def test_refuse_sorcerer_class(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Kael",
            engine=self.engine,
            **sorcerer_creation_kwargs(level=1),
        )
        char = mark_prepared_rechoice_pending(char, pending=True)
        with self.assertRaises(PreparedChoiceError):
            validate_prepared_selection(
                char, self.engine, ["chromatic_orb", "burning_hands"]
            )

    def test_refuse_ranger_class(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Aragorn",
            engine=self.engine,
            **ranger_creation_kwargs(level=2),
        )
        char = mark_prepared_rechoice_pending(char, pending=True)
        with self.assertRaises(PreparedChoiceError):
            validate_prepared_selection(char, self.engine, ["hunters_mark", "cure_wounds"])

    def test_long_rest_sets_pending_for_paladin(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Gareth",
            engine=self.engine,
            **paladin_creation_kwargs(level=1),
        )
        self.assertFalse(is_prepared_rechoice_pending(char))
        char, result = apply_long_rest(char, self.engine)
        self.assertTrue(is_prepared_rechoice_pending(char))
        self.assertTrue(result.prepared_rechoice_pending)

    def test_long_rest_no_pending_for_sorcerer(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Kael",
            engine=self.engine,
            **sorcerer_creation_kwargs(level=1),
        )
        char, result = apply_long_rest(char, self.engine)
        self.assertFalse(is_prepared_rechoice_pending(char))
        self.assertFalse(result.prepared_rechoice_pending)

    def test_autocomplete_reflects_new_preparation(self):
        char = self._pending_druid_quota_three()
        quota = get_player_prepared_quota(char, engine=self.engine)
        pool = list(get_prepared_spell_pool(char, engine=self.engine))
        selection = pool[:quota]
        updated = apply_prepared_selection(
            char,
            self.engine,
            selection,
            require_pending=True,
        )
        castable, _ = compute_spell_autocomplete_availability(
            updated, selection[0], engine=self.engine
        )
        self.assertEqual(castable, SpellAutocompleteAvailability.CASTABLE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
