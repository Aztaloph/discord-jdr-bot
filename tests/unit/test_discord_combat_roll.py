# tests/unit/test_discord_combat_roll.py
"""Tests visibilité combat /roll Discord — Phase 4.8."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import CharacterService
from jdr_engine.application.dto.character_commands import CreateCharacterCommand
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.persistence.character_repository import JsonCharacterRepository
from jdr_engine.rules import RuleEngine

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.handlers.combat_roll import CombatRollFlags, build_trait_display_lines
from interfaces.discord.handlers.dice import execute_roll
from interfaces.discord.settings import DiscordSettings


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestDiscordCombatRoll(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = JsonCharacterRepository(Path(self.tmp.name) / "characters.json")
        self.service = CharacterService(self.repo, self.engine)
        self.ctx = DiscordJdrContext(
            settings=DiscordSettings(use_engine_v2=True),
            rule_engine=self.engine,
            character_service=self.service,
        )
        self.owner_id = 9001

    def tearDown(self):
        self.tmp.cleanup()

    def _create(self, **kwargs):
        choices = kwargs.pop("choices", None)
        defaults = dict(
            owner_id=str(self.owner_id),
            name="Hero",
            race_id="human",
            class_id="fighter",
            level=1,
        )
        defaults.update(kwargs)
        char = self.service.create(CreateCharacterCommand(**defaults))
        if choices:
            char.choices = dict(choices)
            self.repo.save(char)
        return char

    def test_archery_flag_plus_two_and_display(self):
        self._create(
            name="Archer",
            choices={"fighting_style": "archery"},
        )
        result = execute_roll(
            "d20+3",
            "normal",
            self.ctx,
            self.owner_id,
            perso="Archer",
            combat=CombatRollFlags(ranged_weapon=True),
            rng=SequenceRng([12]),
        )
        self.assertEqual(result.modifier, 5)
        self.assertEqual(result.total, 17)
        self.assertTrue(any("Archerie → +2 au toucher" in e for e in result.applied_effects))

    def test_archery_no_style_no_bonus(self):
        self._create(name="SansStyle")
        result = execute_roll(
            "d20+3",
            "normal",
            self.ctx,
            self.owner_id,
            perso="SansStyle",
            combat=CombatRollFlags(ranged_weapon=True),
            rng=SequenceRng([12]),
        )
        self.assertEqual(result.modifier, 3)
        self.assertFalse(any("Archerie" in e for e in result.applied_effects))

    def test_rage_flag_display_and_persists_module_values(self):
        self._create(name="Barb", class_id="barbarian", level=3)
        result = execute_roll(
            "d20",
            "normal",
            self.ctx,
            self.owner_id,
            perso="Barb",
            combat=CombatRollFlags(rage_active=True),
            rng=SequenceRng([10]),
        )
        self.assertTrue(
            any("Rage → +2 dégâts mêlée FOR" in e for e in result.applied_effects)
        )
        self.assertTrue(
            any("résistance bludgeoning" in e for e in result.applied_effects)
        )

    def test_reckless_flag_advantage_and_display(self):
        self._create(name="Barb2", class_id="barbarian", level=2)
        result = execute_roll(
            "d20+4",
            "normal",
            self.ctx,
            self.owner_id,
            perso="Barb2",
            combat=CombatRollFlags(reckless=True),
            rng=SequenceRng([4, 17]),
        )
        self.assertEqual(result.mode, "avantage")
        self.assertEqual(result.total, 21)
        self.assertEqual(result.character_name, "Barb2")
        self.assertTrue(result.traits_active)
        self.assertTrue(
            any("Attaque impétueuse → avantage" in e for e in result.applied_effects)
        )

    def test_2d20_notation_keeps_best_not_sum(self):
        """Bug 1 : 2d20+4 doit garder le max (avantage), pas additionner."""
        self._create(name="CROM", class_id="barbarian", level=2)
        result = execute_roll(
            "2d20+4",
            "normal",
            self.ctx,
            self.owner_id,
            perso="CROM",
            combat=CombatRollFlags(reckless=True),
            rng=SequenceRng([8, 17]),
        )
        self.assertEqual(result.mode, "avantage")
        self.assertEqual(result.kept_value if hasattr(result, "kept_value") else max(
            r for r, k in zip(result.rolls, result.is_kept) if k
        ), 17)
        self.assertEqual(result.total, 21)
        self.assertEqual(result.character_name, "CROM")
        self.assertTrue(
            any("Attaque impétueuse → avantage" in e for e in result.applied_effects)
        )

    def test_d20_impetueux_not_2d20_recommended(self):
        """Chemin attendu : d20+4 + impetueux (pas 2d20 saisi manuellement)."""
        self._create(name="CROM", class_id="barbarian", level=2)
        result = execute_roll(
            "d20+4",
            "normal",
            self.ctx,
            self.owner_id,
            perso="CROM",
            combat=CombatRollFlags(reckless=True),
            rng=SequenceRng([8, 17]),
        )
        self.assertEqual(result.total, 21)
        self.assertIn("2d20 (meilleur gardé)", result.dice_notation)

    def test_sneak_attack_eligible_display_level_3(self):
        self._create(name="Rog", class_id="rogue", level=3)
        result = execute_roll(
            "d20+5",
            "normal",
            self.ctx,
            self.owner_id,
            perso="Rog",
            combat=CombatRollFlags(sneak_attack_eligible=True),
            rng=SequenceRng([14]),
        )
        self.assertTrue(
            any("Attaque sournoise → +2d6 si touché" in e for e in result.applied_effects)
        )

    def test_build_trait_display_simulated_embed_lines(self):
        """Exemple de sortie embed — Rage + Archerie + Sneak Attack."""
        fighter = self._create(
            name="Sim",
            class_id="fighter",
            level=5,
            choices={"fighting_style": "archery"},
        )
        archery_lines = build_trait_display_lines(
            fighter,
            CombatRollFlags(ranged_weapon=True),
            ["+2 jet d'attaque (fighting_style_archery)"],
            roll_mode="normal",
            engine=self.engine,
        )
        self.assertEqual(archery_lines, ["Archerie → +2 au toucher"])

        barb = self.service.create(
            CreateCharacterCommand(
                owner_id=str(self.owner_id),
                name="SimBarb",
                race_id="human",
                class_id="barbarian",
                level=2,
            )
        )
        rage_lines = build_trait_display_lines(
            barb,
            CombatRollFlags(rage_active=True),
            [],
            roll_mode="normal",
            engine=self.engine,
        )
        self.assertIn("Rage → +2 dégâts mêlée FOR, résistance bludgeoning, piercing, slashing", rage_lines)


if __name__ == "__main__":
    unittest.main(verbosity=2)
