# tests/unit/test_discord_dice_handler.py
"""Tests handler /roll Discord → hook d20 + traits (Phase 4.6)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import CharacterService
from jdr_engine.application.dto.character_commands import (
    CreateCharacterCommand,
    ListCharactersQuery,
)
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.dice import DiceError
from jdr_engine.persistence.character_repository import JsonCharacterRepository
from jdr_engine.rules import RuleEngine

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.handlers.dice import (
    execute_roll,
    is_single_d20,
    resolve_character_for_roll,
)
from interfaces.discord.settings import DiscordSettings


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestDiscordDiceHandler(unittest.TestCase):
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
        self.owner_id = 4242

    def tearDown(self):
        self.tmp.cleanup()

    def _create_halfling(self, name: str = "Doudou"):
        return self.service.create(
            CreateCharacterCommand(
                owner_id=str(self.owner_id),
                name=name,
                race_id="halfling",
                class_id="ranger",
                level=1,
            )
        )

    def test_is_single_d20(self):
        self.assertTrue(is_single_d20("d20"))
        self.assertTrue(is_single_d20("1d20+5"))
        self.assertFalse(is_single_d20("2d20"))
        self.assertFalse(is_single_d20("3d6"))

    def test_legacy_roll_without_v2_context(self):
        result = execute_roll("3d6", "normal", None, self.owner_id)
        self.assertFalse(result.traits_active)
        self.assertEqual(len(result.rolls), 3)

    def test_d20_halfling_lucky_via_handler(self):
        self._create_halfling()
        result = execute_roll(
            "d20",
            "normal",
            self.ctx,
            self.owner_id,
            perso="Doudou",
            rng=SequenceRng([1, 13]),
        )
        self.assertTrue(result.traits_active)
        self.assertTrue(result.rerolled)
        self.assertEqual(result.total, 13)
        self.assertEqual(result.character_name, "Doudou")

    def test_d20_halfling_no_lucky_on_high_roll(self):
        self._create_halfling()
        result = execute_roll(
            "d20+2",
            "normal",
            self.ctx,
            self.owner_id,
            perso="Doudou",
            rng=SequenceRng([15]),
        )
        self.assertTrue(result.traits_active)
        self.assertFalse(result.rerolled)
        self.assertEqual(result.total, 17)

    def test_auto_single_character(self):
        self._create_halfling("Solo")
        result = execute_roll(
            "d20",
            "normal",
            self.ctx,
            self.owner_id,
            rng=SequenceRng([1, 7]),
        )
        self.assertTrue(result.traits_active)
        self.assertEqual(result.character_name, "Solo")

    def test_unknown_perso_raises(self):
        with self.assertRaises(DiceError):
            execute_roll("d20", "normal", self.ctx, self.owner_id, perso="Inconnu")

    def test_resolve_character_by_name(self):
        char = self._create_halfling("TestPerso")
        resolved = resolve_character_for_roll(self.ctx, self.owner_id, "TestPerso")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.name, char.name)

    def test_multiple_characters_hint_without_perso(self):
        self._create_halfling("A")
        self.service.create(
            CreateCharacterCommand(
                owner_id=str(self.owner_id),
                name="B",
                race_id="human",
                class_id="fighter",
                level=1,
            )
        )
        result = execute_roll("d20", "normal", self.ctx, self.owner_id, rng=SequenceRng([10]))
        self.assertFalse(result.traits_active)
        self.assertTrue(any("plusieurs_persos" in h for h in result.applied_effects))


if __name__ == "__main__":
    unittest.main(verbosity=2)
