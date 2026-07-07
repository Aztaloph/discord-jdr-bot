# tests/unit/test_rest.py
"""Repos long / court — règles SRD 2014."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.character_service import CharacterService
from tests.helpers.creation import cleric_creation_kwargs, wizard_creation_kwargs
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.rest import (
    RestError,
    apply_long_rest,
    apply_short_rest,
    hit_dice_remaining,
    hit_dice_total,
)
from jdr_engine.rules.spellcasting.state import get_slots_used


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestRestRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)

    def _wizard(self, service: CharacterService, name: str = "Mage"):
        return service.create_from_wizard(
            owner_id="1",
            guild_id="100",
            name=name,
            **wizard_creation_kwargs(),
        )

    def test_long_rest_restores_hp_slots_and_hit_dice(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = CharacterService(
                SqliteCharacterRepository(db), self.engine
            )
            init_database(db)
            char = self._wizard(service)
            char.hp_current = 5
            char.choices = dict(char.choices or {})
            char.choices.setdefault("rest", {})["hit_dice_remaining"] = 1
            char.choices["spellcasting"]["slots_used"] = {"1": 1}
            service.save(char)

            updated, result = apply_long_rest(char, self.engine)
            self.assertEqual(updated.hp_current, updated.hp_max)
            self.assertEqual(get_slots_used(updated), {})
            self.assertGreaterEqual(result.hit_dice_after, result.hit_dice_before)
            self.assertEqual(hit_dice_total(updated), 1)
            self.assertGreaterEqual(hit_dice_remaining(updated), 1)

    def test_long_rest_repeatable_without_cooldown(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = CharacterService(
                SqliteCharacterRepository(db), self.engine
            )
            init_database(db)
            char = self._wizard(service)
            apply_long_rest(char, self.engine)
            char.hp_current = 3
            char.choices["spellcasting"]["slots_used"] = {"1": 1}
            char.choices.setdefault("rest", {})["hit_dice_remaining"] = 0
            updated, result = apply_long_rest(char, self.engine)
            self.assertEqual(updated.hp_current, updated.hp_max)
            self.assertEqual(get_slots_used(updated), {})
            self.assertGreaterEqual(result.hit_dice_after, result.hit_dice_before)

            service.save(updated)
            service.long_rest_on_guild(char.id, "100")
            third = service.get_on_guild(char.id, "100")
            self.assertEqual(third.hp_current, third.hp_max)

    def test_short_rest_spends_hit_dice(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = CharacterService(
                SqliteCharacterRepository(db), self.engine
            )
            init_database(db)
            char = self._wizard(service)
            char.hp_current = 5
            service.save(char)
            rng = SequenceRng([6])
            updated, result = apply_short_rest(
                char, self.engine, 1, rng=rng
            )
            self.assertEqual(result.dice_spent, 1)
            self.assertGreater(result.hp_after, result.hp_before)
            self.assertEqual(updated.hp_current, updated.hp_max)
            self.assertEqual(hit_dice_remaining(updated), 0)
            self.assertEqual(len(result.rolls), 1)

    def test_short_rest_no_spell_slot_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            service = CharacterService(
                SqliteCharacterRepository(db), self.engine
            )
            init_database(db)
            char = service.create_from_wizard(
                owner_id="1",
                guild_id="100",
                name="Clerc",
                **cleric_creation_kwargs(),
            )
            char.choices["spellcasting"]["slots_used"] = {"1": 1}
            service.save(char)
            updated, _ = apply_short_rest(char, self.engine, 0)
            self.assertEqual(get_slots_used(updated), {1: 1})

    def test_service_multiple_characters_long_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bot.db"
            init_database(db)
            service = CharacterService(
                SqliteCharacterRepository(db), self.engine
            )
            a = service.create_from_wizard(
                owner_id="1",
                guild_id="100",
                name="A",
                **wizard_creation_kwargs(),
            )
            b = service.create_from_wizard(
                owner_id="1",
                guild_id="100",
                name="B",
                **cleric_creation_kwargs(),
            )
            self.assertNotEqual(a.id, b.id)
            a.hp_current = 3
            b.hp_current = 4
            service.save(a)
            service.save(b)
            result = service.long_rest_on_guild(a.id, "100")
            self.assertEqual(result.hp_after, a.hp_max)
            reloaded = service.get_on_guild(b.id, "100")
            self.assertEqual(reloaded.hp_current, 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
