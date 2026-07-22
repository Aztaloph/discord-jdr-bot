# tests/unit/test_level_up_asi.py
"""Sous-lot 3 — ASI (Amélioration de caractéristiques) SRD 2014."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import (
    LevelUpError,
    LevelUpPendingChoice,
    apply_level_up,
)
from jdr_engine.rules.character_progression.asi import (
    ASI_POINT_BUDGET,
    AsiValidationError,
    apply_asi_to_base,
    asi_already_applied,
    asi_points_remaining,
    can_decrease_asi,
    can_increase_asi,
    is_asi_pending_complete,
    record_asi_applied,
    requires_asi_at_level,
    validate_asi,
)
from jdr_engine.rules.spellcasting.cast import get_spellcasting_stats
from jdr_engine.rules.spellcasting.prepared_choice import get_player_prepared_quota
from jdr_engine.rules.spellcasting.stats import spell_attack_bonus, spell_save_dc
from tests.helpers.creation import wizard_creation_kwargs


class TestAsiHelpers(unittest.TestCase):
    def test_can_increase_asi_refuses_cap_21(self):
        base = {"int": 19}
        racial = {"int": 1}
        self.assertFalse(can_increase_asi(base, racial, {}, "int"))

    def test_can_increase_asi_refuses_zero_budget(self):
        base = {"int": 15}
        racial = {"int": 1}
        pending = {"int": 2}
        self.assertFalse(can_increase_asi(base, racial, pending, "int"))
        self.assertEqual(asi_points_remaining(pending), 0)

    def test_is_asi_pending_complete_requires_two_points(self):
        self.assertFalse(is_asi_pending_complete({"int": 1}))
        self.assertTrue(is_asi_pending_complete({"int": 2}))
        self.assertTrue(is_asi_pending_complete({"int": 1, "wis": 1}))
        self.assertFalse(is_asi_pending_complete({}))

    def test_can_decrease_asi_only_when_pending_positive(self):
        self.assertFalse(can_decrease_asi({}, "int"))
        self.assertTrue(can_decrease_asi({"int": 1}, "int"))


class TestAsiEmbedBlock(unittest.TestCase):
    def test_touched_stat_shows_base_arrow_and_effective(self):
        from interfaces.discord.components.asi_distribution import (
            AsiDistributionState,
            build_asi_scores_block,
        )

        state = AsiDistributionState(
            original_base=dict.fromkeys(
                ("str", "dex", "con", "int", "wis", "cha"), 10
            )
            | {"int": 15},
            racial_bonuses={"int": 1},
            pending_bonuses=dict.fromkeys(
                ("str", "dex", "con", "int", "wis", "cha"), 0
            )
            | {"int": 2},
        )
        block = build_asi_scores_block(state)
        self.assertIn("**INT** 15→17 (eff. 18 (+4))", block)


class TestAsiUiWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _wizard_asi_pending(self):
        char = finalize_new_character(
            owner_id="42",
            guild_id="900",
            name="Joe",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, subclass="evocation")
        char, _ = apply_level_up(char, self.engine)
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        pending = ctx.exception.pending
        self.assertEqual(pending.choice_type, "ability_score_improvement")
        return pending

    def test_build_pending_ui_uses_asi_distribution_view(self):
        from unittest.mock import MagicMock

        from interfaces.discord.components.asi_distribution import (
            AsiConfirmButton,
            AsiDistributionView,
        )
        from interfaces.discord.views.level_up_choice import build_level_up_pending_ui

        pending = self._wizard_asi_pending()

        async def noop_confirm(_interaction, _state, _choice):
            return None

        view, embed = build_level_up_pending_ui(
            pending,
            engine=self.engine,
            character_service=MagicMock(),
            guild_id="900",
            character_id=pending.character.id,
            on_asi_confirm=noop_confirm,
        )
        self.assertIsInstance(view, AsiDistributionView)
        self.assertIn("Budget ASI", embed.description or "")
        self.assertIn("**INT**", embed.description or "")
        confirm = next(c for c in view.children if isinstance(c, AsiConfirmButton))
        self.assertTrue(confirm.disabled)
        plus_buttons = [
            c
            for c in view.children
            if getattr(c, "label", "").endswith("+")
        ]
        self.assertEqual(len(plus_buttons), 6)

    def test_level_up_choice_view_rejects_asi_pending(self):
        from unittest.mock import MagicMock

        from interfaces.discord.views.level_up_choice import LevelUpChoiceView

        pending = self._wizard_asi_pending()
        with self.assertRaises(ValueError):
            LevelUpChoiceView(
                pending,
                self.engine,
                MagicMock(),
                "900",
                pending.character.id,
            )


class TestAsiPure(unittest.TestCase):
    def test_asi_levels_set(self):
        from jdr_engine.rules.character_progression.asi import ASI_LEVELS

        self.assertEqual(ASI_LEVELS, frozenset({4, 8, 12, 16, 19}))
        self.assertTrue(requires_asi_at_level(4))
        self.assertFalse(requires_asi_at_level(5))

    def test_validate_plus_two(self):
        bonuses = validate_asi({"int": 15}, {"int": 1}, {"int": 2})
        self.assertEqual(bonuses, {"int": 2})

    def test_validate_plus_one_twice(self):
        bonuses = validate_asi(
            {"int": 14, "wis": 12},
            {"int": 1, "wis": 1},
            {"int": 1, "wis": 1},
        )
        self.assertEqual(bonuses, {"int": 1, "wis": 1})

    def test_reject_invalid_total(self):
        with self.assertRaises(AsiValidationError):
            validate_asi({"int": 15}, {"int": 1}, {"int": 1})

    def test_reject_cap_over_20_effective(self):
        with self.assertRaises(AsiValidationError):
            validate_asi({"int": 19}, {"int": 1}, {"int": 2})

    def test_apply_asi_touches_base_only(self):
        base = AbilityScores(scores={"int": 15, "str": 10, "dex": 10, "con": 10, "wis": 10, "cha": 10})
        updated = apply_asi_to_base(base, {"int": 2})
        self.assertEqual(updated.scores["int"], 17)

    def test_idempotence_record(self):
        choices = record_asi_applied({}, 4, {"int": 2})
        self.assertTrue(asi_already_applied(choices, 4))
        choices2 = record_asi_applied(choices, 4, {"int": 2})
        self.assertEqual(len(choices2["asi_applied"]), 1)


class TestAsiLevelUpIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def _wizard_level_3(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="900",
            name="Joe",
            engine=self.engine,
            **wizard_creation_kwargs(level=3, specialization="evocation"),
        )
        self.assertEqual(char.level, 3)
        return char

    def test_level_3_to_4_requires_asi_pending(self):
        char = self._wizard_level_3()
        with self.assertRaises(LevelUpPendingChoice) as ctx:
            apply_level_up(char, self.engine)
        self.assertEqual(ctx.exception.pending.choice_type, "ability_score_improvement")
        self.assertEqual(ctx.exception.pending.target_level, 4)

    def test_level_4_asi_plus_two_int_updates_sheet_and_spell_stats(self):
        char = self._wizard_level_3()
        _, _, dc_before = get_spellcasting_stats(char, self.engine)
        self.assertEqual(get_player_prepared_quota(char, engine=self.engine), 6)

        char, result = apply_level_up(char, self.engine, asi_choice={"int": 2})
        self.assertEqual(result.new_level, 4)

        sheet = build_character_sheet(char, self.engine)
        self.assertEqual(char.ability_scores.scores["int"], 17)
        self.assertEqual(sheet.ability_scores_base["int"], 17)
        self.assertEqual(sheet.ability_scores["int"], 18)
        self.assertEqual(sheet.ability_modifiers["int"], 4)

        mod, attack, dc = get_spellcasting_stats(char, self.engine)
        prof = self.engine.get_proficiency_bonus(4)
        self.assertEqual(prof, 2)
        self.assertEqual(mod, 4)
        self.assertEqual(dc, spell_save_dc(prof, mod))
        self.assertEqual(attack, spell_attack_bonus(prof, mod))
        self.assertEqual(dc, dc_before + 1)
        # niv. 3 (mod +3 → quota 6) → niv. 4 (mod +4 → quota 8) : +1 mod, +1 niveau
        self.assertEqual(get_player_prepared_quota(char, engine=self.engine), 8)

        applied = (char.choices or {}).get("asi_applied") or []
        self.assertEqual(applied, [{"level": 4, "bonuses": {"int": 2}}])

    def test_asi_idempotent_on_reapply(self):
        char = self._wizard_level_3()
        char, _ = apply_level_up(char, self.engine, asi_choice={"int": 2})
        scores_after = dict(char.ability_scores.scores)
        char, result = apply_level_up(char, self.engine)
        self.assertEqual(result.new_level, 5)
        self.assertEqual(dict(char.ability_scores.scores), scores_after)

    def test_level_5_no_asi_pending(self):
        char = self._wizard_level_3()
        char, _ = apply_level_up(char, self.engine, asi_choice={"int": 2})
        char, _ = apply_level_up(char, self.engine)
        self.assertEqual(char.level, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
