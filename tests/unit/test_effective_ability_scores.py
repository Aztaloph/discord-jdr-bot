# tests/unit/test_effective_ability_scores.py
"""Sous-lot ASI 1 — scores effectifs (base + racial) pour sorts et préparés."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.effective_scores import (
    compute_effective_ability_scores,
    effective_ability_modifier,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.effective_scores import (
    get_effective_ability_modifier,
    get_effective_ability_scores,
)
from jdr_engine.rules.spellcasting.cast import get_spellcasting_stats
from jdr_engine.rules.spellcasting.model import wizard_prepared_capacity
from jdr_engine.rules.spellcasting.prepared_choice import get_player_prepared_quota
from jdr_engine.rules.spellcasting.stats import spell_attack_bonus, spell_save_dc
from tests.helpers.creation import wizard_creation_kwargs


class TestComputeEffectiveScores(unittest.TestCase):
    def test_applies_racial_on_base_only(self):
        base = dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
        base["int"] = 15
        effective = compute_effective_ability_scores(base, {"int": 1, "str": 1})
        self.assertEqual(effective["int"], 16)
        self.assertEqual(effective["str"], 11)

    def test_effective_modifier(self):
        scores = {"int": 16, "str": 10}
        self.assertEqual(effective_ability_modifier(scores, "int"), 3)


class TestEffectiveScoresIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _human_wizard(self, *, base_int: int, level: int = 1) -> Character:
        scores = dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
        scores["int"] = base_int
        return Character(
            owner_id="1",
            name="Merlin",
            race_id="human",
            class_id="wizard",
            level=level,
            ability_scores=AbilityScores(scores=scores),
            choices={
                "spellcasting": {
                    "cantrips_known": ["fire_bolt"],
                    "spells_prepared": ["magic_missile"],
                    "slots_used": {},
                }
            },
        )

    def test_base_only_differs_from_effective_for_human(self):
        char = self._human_wizard(base_int=15)
        base = char.ability_scores.scores["int"]
        effective = get_effective_ability_scores(char, self.engine)["int"]
        self.assertEqual(base, 15)
        self.assertEqual(effective, 16)

    def test_spellcasting_stats_use_effective_int_not_base(self):
        # Base INT 14 (+2) + humain +1 → effectif 15 (+2) — distinct du base seul (+2 vs +2 same)
        # Base INT 15 (+2) + humain +1 → effectif 16 (+3)
        char = self._human_wizard(base_int=15)
        mod, attack, dc = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod, 3)
        self.assertEqual(attack, spell_attack_bonus(2, 3))
        self.assertEqual(dc, spell_save_dc(2, 3))

    def test_prepared_quota_uses_effective_mod(self):
        char = self._human_wizard(base_int=15, level=1)
        mod = get_effective_ability_modifier(char, self.engine, "int")
        expected = wizard_prepared_capacity(mod, 1)
        self.assertEqual(get_player_prepared_quota(char, engine=self.engine), expected)
        self.assertEqual(expected, 4)

    def test_proficiency_bonus_level_5_spellcasting_stats(self):
        """Maîtrise +3 au niv. 5 — DD et attaque via get_spellcasting_stats."""
        char = self._human_wizard(base_int=15, level=5)
        prof = self.engine.get_proficiency_bonus(5)
        self.assertEqual(prof, 3)
        mod, attack, dc = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod, 3)
        self.assertEqual(attack, spell_attack_bonus(3, 3))
        self.assertEqual(dc, spell_save_dc(3, 3))
        self.assertEqual(dc, 14)

    def test_proficiency_bonus_level_5_formula(self):
        """Maîtrise +3 au niv. 5 (compendium) — DD/attaque = prof + mod effectif."""
        char = self._human_wizard(base_int=15, level=5)
        prof = self.engine.get_proficiency_bonus(5)
        self.assertEqual(prof, 3)
        mod = get_effective_ability_modifier(char, self.engine, "int")
        self.assertEqual(mod, 3)
        self.assertEqual(spell_save_dc(prof, mod), 14)
        self.assertEqual(spell_attack_bonus(prof, mod), 6)

    def test_finalize_character_matches_sheet_effective_scores(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Joe",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        from jdr_engine.rules.calculator import build_character_sheet

        sheet = build_character_sheet(char, self.engine)
        effective = get_effective_ability_scores(char, self.engine)
        self.assertEqual(effective, sheet.ability_scores)


if __name__ == "__main__":
    unittest.main(verbosity=2)
