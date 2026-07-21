# tests/unit/test_p2f0_wizard_prepared_rechoice.py
"""P2f-0 — magicien re-prépare depuis son grimoire (/preparer-sorts)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.rest import apply_long_rest
from jdr_engine.rules.spellcasting.model import wizard_prepared_capacity
from jdr_engine.rules.spellcasting.pools import get_filtered_leveled_pool
from jdr_engine.rules.spellcasting.prepared_choice import (
    PreparedChoiceError,
    apply_prepared_selection,
    build_prepared_choice_context,
    get_prepared_spell_pool,
    get_player_prepared_quota,
    is_prepared_rechoice_pending,
    mark_prepared_rechoice_pending,
    requires_prepared_rechoice_class,
    validate_prepared_selection,
)
from jdr_engine.rules.spellcasting.state import (
    get_spellbook,
    get_spells_prepared_list,
)
from tests.helpers.creation import wizard_creation_kwargs


def _wizard(
    level: int,
    spellcasting: dict,
    *,
    int_score: int = 15,
) -> Character:
    return Character(
        owner_id="1",
        name="Gandalf",
        race_id="human",
        class_id="wizard",
        level=level,
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
        choices={"spellcasting": spellcasting},
    )


class TestWizardPreparedRechoice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_wizard_requires_rechoice_class(self):
        self.assertTrue(requires_prepared_rechoice_class("wizard"))

    def test_pool_is_spellbook_not_class_list(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "burning_hands"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
        )
        pool = get_prepared_spell_pool(char, engine=self.engine)
        class_pool = get_filtered_leveled_pool("wizard", 1, engine=self.engine)
        self.assertEqual(set(pool), {"magic_missile", "burning_hands"})
        self.assertIn("shield", class_pool)
        self.assertNotIn("shield", pool)

    def test_pool_filters_by_spell_level(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "scorching_ray"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
        )
        pool = get_prepared_spell_pool(char, engine=self.engine)
        self.assertIn("magic_missile", pool)
        self.assertNotIn("scorching_ray", pool)

    def test_pool_excludes_cantrips(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
        )
        pool = get_prepared_spell_pool(char, engine=self.engine)
        self.assertNotIn("fire_bolt", pool)

    def test_quota_uses_wizard_prepared_capacity(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "burning_hands", "shield", "detect_magic"],
                "spells_prepared": ["magic_missile", "burning_hands", "shield", "detect_magic"],
                "slots_used": {},
            },
            int_score=15,
        )
        self.assertEqual(get_player_prepared_quota(char), wizard_prepared_capacity(2, 1))

    def test_valid_selection_from_spellbook_persisted(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "burning_hands", "shield", "detect_magic"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
            int_score=15,
        )
        char = mark_prepared_rechoice_pending(char, pending=True)
        quota = get_player_prepared_quota(char)
        selection = ["magic_missile", "burning_hands", "shield", "detect_magic"][:quota]
        updated = apply_prepared_selection(
            char, self.engine, selection, require_pending=True
        )
        self.assertEqual(get_spells_prepared_list(updated), selection)
        self.assertFalse(is_prepared_rechoice_pending(updated))

    def test_refuse_spell_not_in_spellbook(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "burning_hands", "shield", "detect_magic"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
            int_score=15,
        )
        char = mark_prepared_rechoice_pending(char, pending=True)
        quota = get_player_prepared_quota(char)
        with self.assertRaises(PreparedChoiceError) as ctx:
            validate_prepared_selection(
                char,
                self.engine,
                ["magic_missile", "burning_hands", "chromatic_orb"][:quota],
            )
        self.assertIn("grimoire", str(ctx.exception).lower())

    def test_refuse_wrong_quota(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "burning_hands", "shield", "detect_magic"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
            int_score=15,
        )
        char = mark_prepared_rechoice_pending(char, pending=True)
        with self.assertRaises(PreparedChoiceError) as ctx:
            validate_prepared_selection(char, self.engine, ["magic_missile"])
        self.assertIn("exactement", str(ctx.exception).lower())

    def test_refuse_without_pending_flag(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "burning_hands", "shield", "detect_magic"],
                "spells_prepared": ["magic_missile", "burning_hands", "shield", "detect_magic"],
                "slots_used": {},
            },
            int_score=15,
        )
        quota = get_player_prepared_quota(char)
        with self.assertRaises(PreparedChoiceError) as ctx:
            validate_prepared_selection(
                char,
                self.engine,
                ["magic_missile", "burning_hands", "shield", "detect_magic"][:quota],
            )
        self.assertIn("repos long", str(ctx.exception).lower())

    def test_long_rest_sets_pending_for_wizard(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        self.assertFalse(is_prepared_rechoice_pending(char))
        char, result = apply_long_rest(char, self.engine)
        self.assertTrue(is_prepared_rechoice_pending(char))
        self.assertTrue(result.prepared_rechoice_pending)

    def test_legacy_wizard_spellbook_fallback(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spells_prepared": ["magic_missile", "burning_hands", "shield", "detect_magic"],
                "slots_used": {},
            },
            int_score=15,
        )
        self.assertEqual(
            get_spellbook(char),
            ["magic_missile", "burning_hands", "shield", "detect_magic"],
        )
        pool = get_prepared_spell_pool(char, engine=self.engine)
        self.assertEqual(
            set(pool),
            {"magic_missile", "burning_hands", "shield", "detect_magic"},
        )

    def test_empty_spellbook_yields_empty_pool(self):
        char = _wizard(
            1,
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": [],
                "spells_prepared": [],
                "slots_used": {},
            },
        )
        char = mark_prepared_rechoice_pending(char, pending=True)
        pool = get_prepared_spell_pool(char, engine=self.engine)
        self.assertEqual(pool, ())
        ctx = build_prepared_choice_context(char, engine=self.engine)
        self.assertEqual(ctx.pool, ())
        with self.assertRaises(PreparedChoiceError) as exc:
            validate_prepared_selection(char, self.engine, ["magic_missile"])
        self.assertIn("grimoire", str(exc.exception).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
