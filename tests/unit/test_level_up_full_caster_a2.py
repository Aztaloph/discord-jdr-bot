# tests/unit/test_level_up_full_caster_a2.py
"""Lot A2 — cap niv. 20, progression mage 6–20, ASI paliers 8/12/16/19."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_progression import (
    MAX_CHARACTER_LEVEL,
    LevelUpError,
    LevelUpPendingChoice,
    apply_level_up,
)
from jdr_engine.rules.character_progression.asi import ASI_LEVELS, requires_asi_at_level
from jdr_engine.rules.effective_scores import get_effective_ability_modifier
from jdr_engine.rules.rest.state import hit_dice_total
from jdr_engine.rules.spellcasting import cast_spell
from jdr_engine.rules.spellcasting.model import (
    cantrips_known_capacity,
    wizard_prepared_capacity,
    wizard_spellbook_capacity_at_level,
)
from jdr_engine.rules.spellcasting.prepared_choice import get_player_prepared_quota
from jdr_engine.rules.spellcasting.slots import FULL_CASTER_SPELL_SLOTS, get_max_spell_slots
from jdr_engine.rules.spellcasting.spells_catalog import WIZARD_CANTRIP_IDS, WIZARD_SPELLBOOK_POOL
from jdr_engine.rules.spellcasting.state import get_cantrips_known, get_spellbook

from tests.helpers.level_up import wizard_at_level


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


PROFICIENCY_BY_LEVEL: dict[int, int] = {
    level: (
        2
        if level <= 4
        else 3
        if level <= 8
        else 4
        if level <= 12
        else 5
        if level <= 16
        else 6
    )
    for level in range(1, 21)
}


class TestFullCasterCapTwenty(unittest.TestCase):
    def test_max_character_level_is_twenty(self):
        self.assertEqual(MAX_CHARACTER_LEVEL, 20)


class TestWizardProgressionSixToTwenty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_each_level_matches_a1_tables(self):
        for level in range(6, 21):
            with self.subTest(level=level):
                char = wizard_at_level(self.engine, level)
                self.assertEqual(char.level, level)
                self.assertEqual(
                    get_max_spell_slots("wizard", level),
                    FULL_CASTER_SPELL_SLOTS[level],
                )
                expected_cantrips = min(
                    cantrips_known_capacity("wizard", level),
                    len(WIZARD_CANTRIP_IDS),
                )
                expected_spellbook = min(
                    wizard_spellbook_capacity_at_level(level),
                    len(WIZARD_SPELLBOOK_POOL),
                )
                self.assertEqual(len(get_cantrips_known(char)), expected_cantrips)
                self.assertEqual(len(get_spellbook(char)), expected_spellbook)
                int_mod = get_effective_ability_modifier(char, self.engine, "int")
                self.assertEqual(
                    get_player_prepared_quota(char, engine=self.engine),
                    wizard_prepared_capacity(int_mod, level),
                )
                self.assertEqual(
                    self.engine.get_proficiency_bonus(level),
                    PROFICIENCY_BY_LEVEL[level],
                )
                self.assertEqual(hit_dice_total(char), level)

    def test_curated_pool_caps_spellbook_and_cantrips_before_srd_quota(self):
        """Catalogue curated (Lot B) < quotas SRD niv. 20 — signal pour axe B."""
        char = wizard_at_level(self.engine, 20)
        self.assertEqual(len(get_spellbook(char)), len(WIZARD_SPELLBOOK_POOL))
        self.assertLess(len(get_spellbook(char)), wizard_spellbook_capacity_at_level(20))
        self.assertEqual(len(get_cantrips_known(char)), len(WIZARD_CANTRIP_IDS))
        self.assertLess(
            len(get_cantrips_known(char)),
            cantrips_known_capacity("wizard", 20),
        )

    def test_level_20_blocks_further_level_up(self):
        char = wizard_at_level(self.engine, 20)
        with self.assertRaises(LevelUpError):
            apply_level_up(char, self.engine)


class TestAsiTiersEightToNineteen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def test_asi_levels_include_all_srd_paliers(self):
        self.assertEqual(ASI_LEVELS, frozenset({4, 8, 12, 16, 19}))

    def test_requires_asi_pending_at_level_8(self):
        self._assert_asi_pending_before(8)

    def test_requires_asi_pending_at_level_12(self):
        self._assert_asi_pending_before(12)

    def test_requires_asi_pending_at_level_16(self):
        self._assert_asi_pending_before(16)

    def test_requires_asi_pending_at_level_19(self):
        self._assert_asi_pending_before(19)

    def _assert_asi_pending_before(self, asi_level: int) -> None:
        char = wizard_at_level(self.engine, asi_level - 1)
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        pending = ctx.exception.pending
        self.assertEqual(pending.choice_type, "ability_score_improvement")
        self.assertEqual(pending.target_level, asi_level)
        self.assertTrue(requires_asi_at_level(asi_level))

    def test_five_asi_records_after_level_20(self):
        char = wizard_at_level(self.engine, 20)
        applied = (char.choices or {}).get("asi_applied") or []
        self.assertEqual(len(applied), 5)
        levels = {entry["level"] for entry in applied}
        self.assertEqual(levels, {4, 8, 12, 16, 19})

    def test_asi_idempotent_after_level_8(self):
        self._assert_asi_idempotent_step(8)

    def test_asi_idempotent_after_level_12(self):
        self._assert_asi_idempotent_step(12)

    def test_asi_idempotent_after_level_16(self):
        self._assert_asi_idempotent_step(16)

    def test_asi_idempotent_after_level_19(self):
        self._assert_asi_idempotent_step(19)

    def _assert_asi_idempotent_step(self, after_level: int) -> None:
        char = wizard_at_level(self.engine, after_level)
        scores_after_asi = dict(char.ability_scores.scores)
        char, result = apply_level_up(char, self.engine)
        self.assertEqual(result.new_level, after_level + 1)
        self.assertEqual(dict(char.ability_scores.scores), scores_after_asi)

    def test_reapply_same_asi_level_does_not_duplicate_record(self):
        char = wizard_at_level(self.engine, 8)
        applied_once = list((char.choices or {}).get("asi_applied") or [])
        self.assertEqual(len(applied_once), 2)
        char, _ = apply_level_up(char, self.engine)
        applied_twice = (char.choices or {}).get("asi_applied") or []
        self.assertEqual(len(applied_twice), 2)


class TestCantripScalingStillWorksHighLevel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _wizard_with_level(self, level: int) -> Character:
        scores = dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
        scores["int"] = 16
        return Character(
            owner_id="1",
            name="Merlin",
            race_id="human",
            class_id="wizard",
            level=level,
            hp_current=20,
            hp_max=20,
            ability_scores=AbilityScores(scores=scores),
            choices={
                "spellcasting": {
                    "cantrips_known": ["fire_bolt"],
                    "spellbook": ["magic_missile"],
                    "spells_prepared": ["magic_missile"],
                    "slots_used": {},
                }
            },
        )

    def test_fire_bolt_3d10_at_level_11(self):
        char = self._wizard_with_level(11)
        result = cast_spell(
            char, "fire_bolt", self.engine, rng=SequenceRng([12, 4, 5, 6]), persist_slots=False
        )
        self.assertEqual(result.damage_notation, "3d10")
        self.assertEqual(len(result.damage_rolls), 3)

    def test_fire_bolt_4d10_at_level_17(self):
        char = self._wizard_with_level(17)
        result = cast_spell(
            char, "fire_bolt", self.engine, rng=SequenceRng([12, 3, 4, 5, 6]), persist_slots=False
        )
        self.assertEqual(result.damage_notation, "4d10")
        self.assertEqual(len(result.damage_rolls), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
