# tests/unit/test_spellcasting_p1a_state.py
"""Passe 2 / Lot P1a — lecture family-aware + fallbacks legacy (state.py)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.spellcasting.cast import SpellCastError, cast_spell
from jdr_engine.rules.spellcasting.state import (
    format_spellcasting_detail,
    get_spells_known,
    get_spells_prepared_list,
    list_castable_spell_ids,
    list_spell_autocomplete_ids,
    spell_is_known,
)
from tests.helpers.creation import (
    druid_creation_kwargs,
    paladin_creation_kwargs,
    ranger_creation_kwargs,
    warlock_creation_kwargs,
    wizard_creation_kwargs,
)


def _caster(
    class_id: str,
    spellcasting: dict,
    *,
    level: int = 1,
    scores: dict[str, int] | None = None,
) -> Character:
    base_scores = scores or dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
    return Character(
        owner_id="1",
        name="Legacy",
        race_id="human",
        class_id=class_id,
        level=level,
        ability_scores=AbilityScores(scores=base_scores),
        choices={"spellcasting": spellcasting},
    )


class TestLegacyPreparedFallback(unittest.TestCase):
    """Famille PREPARED — repli spells_known si spells_prepared absent/vide."""

    def test_druid_legacy_spells_known_only(self):
        char = _caster(
            "druid",
            {
                "cantrips_known": ["druidcraft", "produce_flame"],
                "spells_known": ["entangle", "cure_wounds", "faerie_fire"],
                "slots_used": {},
            },
            level=1,
            scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 15, "cha": 10},
        )
        self.assertEqual(get_spells_prepared_list(char), [])
        known = get_spells_known(char)
        self.assertEqual(known, ["entangle", "cure_wounds", "faerie_fire"])
        self.assertTrue(spell_is_known(char, "entangle"))
        self.assertFalse(spell_is_known(char, "flaming_sphere"))
        self.assertEqual(
            list_castable_spell_ids(char),
            ["druidcraft", "produce_flame", "entangle", "cure_wounds", "faerie_fire"],
        )

    def test_paladin_legacy_both_keys_same_content(self):
        spells = ["bless", "cure_wounds"]
        char = _caster(
            "paladin",
            {
                "cantrips_known": [],
                "spells_known": spells,
                "spells_prepared": spells,
                "slots_used": {},
            },
            level=2,
            scores={"str": 15, "dex": 10, "con": 14, "int": 10, "wis": 10, "cha": 14},
        )
        self.assertEqual(get_spells_known(char), spells)
        self.assertTrue(spell_is_known(char, "bless"))
        self.assertFalse(spell_is_known(char, "detect_magic"))

    def test_paladin_legacy_spells_known_only(self):
        char = _caster(
            "paladin",
            {
                "spells_known": ["bless", "cure_wounds"],
                "slots_used": {},
            },
            level=2,
        )
        self.assertEqual(get_spells_known(char), ["bless", "cure_wounds"])
        self.assertTrue(spell_is_known(char, "cure_wounds"))

    def test_prepared_takes_priority_over_legacy_known(self):
        char = _caster(
            "druid",
            {
                "spells_prepared": ["entangle"],
                "spells_known": ["entangle", "cure_wounds", "faerie_fire"],
                "slots_used": {},
            },
            level=1,
        )
        self.assertEqual(get_spells_known(char), ["entangle"])
        self.assertFalse(spell_is_known(char, "cure_wounds"))


class TestLegacyKnownFallback(unittest.TestCase):
    """Famille KNOWN_FIXED — repli spells_prepared si spells_known absent/vide."""

    def test_ranger_legacy_duplicate_keys(self):
        spells = ["hunters_mark", "cure_wounds"]
        char = _caster(
            "ranger",
            {
                "spells_known": spells,
                "spells_prepared": spells,
                "slots_used": {},
            },
            level=2,
        )
        self.assertEqual(get_spells_known(char), spells)
        self.assertTrue(spell_is_known(char, "hunters_mark"))

    def test_ranger_legacy_spells_prepared_only(self):
        char = _caster(
            "ranger",
            {
                "spells_prepared": ["hunters_mark", "cure_wounds"],
                "slots_used": {},
            },
            level=2,
        )
        self.assertEqual(get_spells_known(char), ["hunters_mark", "cure_wounds"])

    def test_bard_legacy_spells_prepared_only(self):
        char = _caster(
            "bard",
            {
                "cantrips_known": ["vicious_mockery"],
                "spells_prepared": ["healing_word", "cure_wounds"],
                "slots_used": {},
            },
            level=1,
        )
        self.assertEqual(get_spells_known(char), ["healing_word", "cure_wounds"])
        self.assertTrue(spell_is_known(char, "healing_word"))

    def test_warlock_legacy_spells_known(self):
        char = _caster(
            "warlock",
            {
                "cantrips_known": ["eldritch_blast", "prestidigitation"],
                "spells_known": ["hex", "armor_of_agathys"],
                "slots_used": {},
                "pact_magic": True,
            },
            level=1,
            scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 10, "cha": 15},
        )
        known = get_spells_known(char)
        self.assertEqual(known, ["hex", "armor_of_agathys"])
        self.assertTrue(spell_is_known(char, "hex"))
        self.assertFalse(spell_is_known(char, "darkness"))


class TestUnchangedCasters(unittest.TestCase):
    """Clerc / magicien — comportement inchangé (non-régression P1a)."""

    def test_cleric_prepared_and_domain(self):
        char = _caster(
            "cleric",
            {
                "cantrips_known": ["sacred_flame"],
                "spells_prepared": ["inflict_wounds"],
                "domain_spells": ["bless", "cure_wounds"],
                "slots_used": {},
            },
            level=1,
        )
        known = get_spells_known(char)
        self.assertIn("bless", known)
        self.assertIn("inflict_wounds", known)
        self.assertNotIn("bless", get_spells_prepared_list(char))
        self.assertTrue(spell_is_known(char, "bless"))
        self.assertTrue(spell_is_known(char, "inflict_wounds"))

    def test_wizard_autocomplete_still_includes_spellbook(self):
        """P1f changera l'autocomplete mage — pas P1a."""
        char = _caster(
            "wizard",
            {
                "cantrips_known": ["fire_bolt"],
                "spellbook": ["magic_missile", "burning_hands", "shield"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            },
            level=1,
        )
        autocomplete = list_spell_autocomplete_ids(char)
        self.assertIn("fire_bolt", autocomplete)
        self.assertIn("magic_missile", autocomplete)
        self.assertIn("burning_hands", autocomplete)
        self.assertIn("shield", autocomplete)
        self.assertNotIn("burning_hands", get_spells_known(char))


class TestFinalizeParity(unittest.TestCase):
    """Persos créés par finalize — mêmes listes qu'avant P1a."""

    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_finalize_druid_castable_list(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Rowan",
            engine=self.engine,
            **druid_creation_kwargs(level=1),
        )
        castable = list_castable_spell_ids(char)
        self.assertIn("druidcraft", castable)
        self.assertIn("entangle", castable)
        self.assertIn("cure_wounds", castable)
        self.assertNotIn("flaming_sphere", castable)

    def test_finalize_warlock_castable_list(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=1),
        )
        castable = list_castable_spell_ids(char)
        self.assertIn("eldritch_blast", castable)
        self.assertIn("hex", castable)
        self.assertIn("armor_of_agathys", castable)

    def test_finalize_druid_cast_still_works(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Rowan",
            engine=self.engine,
            **druid_creation_kwargs(level=1),
        )
        result = cast_spell(char, "cure_wounds", self.engine, rng=lambda a, b: b)
        self.assertIsNotNone(result.healing_total)

    def test_finalize_wizard_unprepared_still_rejected(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        book = char.choices["spellcasting"].get("spellbook") or []
        prepared = set(get_spells_prepared_list(char))
        unprepared = next(s for s in book if s not in prepared)
        with self.assertRaises(SpellCastError):
            cast_spell(char, unprepared, self.engine)


class TestFormatSpellcastingDetailLegacy(unittest.TestCase):
    def test_druid_legacy_detail_unchanged(self):
        char = _caster(
            "druid",
            {
                "cantrips_known": ["druidcraft"],
                "spells_known": ["entangle", "cure_wounds"],
                "slots_used": {},
            },
            level=1,
            scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 15, "cha": 10},
        )
        detail = format_spellcasting_detail(char)
        self.assertIn("Préparation (affichage)", detail)
        self.assertIn("Sorts accessibles : entangle, cure_wounds", detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
