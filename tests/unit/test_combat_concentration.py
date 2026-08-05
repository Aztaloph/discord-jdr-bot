# tests/unit/test_combat_concentration.py
"""Lot C5 — rupture de concentration sur dégâts (save CON)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import ConcentrationBroken, DamageDealt
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.concentration_save import concentration_save_dc
from jdr_engine.rules.spellcasting.state import get_spellcasting_state


class RandSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self, a: int, b: int) -> int:
        if not self._values:
            raise RuntimeError("RandSequence épuisé")
        return self._values.pop(0)


class InitiativeSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self) -> int:
        if not self._values:
            raise RuntimeError("InitiativeSequence épuisé")
        return self._values.pop(0)


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _ranger(*, name: str = "Rodeur", con: int = 12) -> Character:
    return Character(
        owner_id="111",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="ranger",
        level=2,
        ability_scores=AbilityScores(
            scores={
                "str": 12,
                "dex": 16,
                "con": con,
                "int": 10,
                "wis": 14,
                "cha": 10,
            }
        ),
        hp_current=24,
        hp_max=24,
        choices={
            "spellcasting": {
                "spells_known": ["hunters_mark"],
                "slots_used": {},
            }
        },
    )


def _wizard(*, name: str = "Mage") -> Character:
    return Character(
        owner_id="112",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="wizard",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 8,
                "dex": 14,
                "con": 12,
                "int": 16,
                "wis": 10,
                "cha": 10,
            }
        ),
        hp_current=20,
        hp_max=20,
        choices={
            "spellcasting": {
                "cantrips_known": ["fire_bolt"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            }
        },
    )


class TestConcentrationSaveRules(unittest.TestCase):
    def test_dc_minimum_ten(self) -> None:
        self.assertEqual(concentration_save_dc(4), 10)
        self.assertEqual(concentration_save_dc(10), 10)

    def test_dc_half_damage_rounded_down(self) -> None:
        self.assertEqual(concentration_save_dc(22), 11)
        self.assertEqual(concentration_save_dc(23), 11)

    def test_zero_damage_no_dc(self) -> None:
        self.assertEqual(concentration_save_dc(0), 0)


class TestCombatConcentrationBreak(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.bus.subscribe(DamageDealt, self.events.append)
        self.bus.subscribe(ConcentrationBroken, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.ranger = _ranger(name="Alice")
        self.wizard = _wizard(name="Bob")
        self.char_repo.save(self.ranger)
        self.char_repo.save(self.wizard)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _active_fight(self) -> tuple[str, str, int]:
        state = self.manager.create_combat(
            "guild1", "channel1", [self.ranger.id, self.wizard.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id), rng=InitiativeSequence([10, 8])
        )
        ranger_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.ranger.id
        )
        wizard_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.wizard.id
        )
        return ranger_id, wizard_id, int(state.combat_id)

    def _mark_and_concentrate(
        self, ranger_id: str, wizard_id: str, combat_id: int
    ) -> None:
        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)

    def test_successful_save_keeps_concentration(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()
        self._mark_and_concentrate(ranger_id, wizard_id, combat_id)

        state, _ = self.manager.apply_damage(
            combat_id,
            ranger_id,
            damage_amount=10,
            source_id=wizard_id,
            rng=RandSequence([9]),
        )
        self.assertEqual(
            state.combatants[ranger_id].concentration_spell_id, "hunters_mark"
        )
        self.assertIn("concentration", get_spellcasting_state(
            self.char_repo.get_by_id(self.ranger.id)  # type: ignore[arg-type]
        ))
        self.assertEqual(len(self.events), 1)
        self.assertIsInstance(self.events[0], DamageDealt)

    def test_failed_save_breaks_concentration(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()
        self._mark_and_concentrate(ranger_id, wizard_id, combat_id)

        state, _ = self.manager.apply_damage(
            combat_id,
            ranger_id,
            damage_amount=22,
            source_id=wizard_id,
            rng=RandSequence([3]),
        )
        self.assertIsNone(state.combatants[ranger_id].concentration_spell_id)
        self.assertFalse(
            any(
                effect.effect_id == "hunters_mark" and effect.target_id == wizard_id
                for effect in state.active_effects
            )
        )
        reloaded_char = self.char_repo.get_by_id(self.ranger.id)
        assert reloaded_char is not None
        self.assertNotIn("concentration", get_spellcasting_state(reloaded_char))

        self.assertEqual(len(self.events), 2)
        self.assertIsInstance(self.events[0], DamageDealt)
        broken = self.events[1]
        self.assertIsInstance(broken, ConcentrationBroken)
        assert isinstance(broken, ConcentrationBroken)
        self.assertEqual(broken.combatant_id, ranger_id)
        self.assertEqual(broken.spell_id, "hunters_mark")
        self.assertEqual(broken.damage_taken, 22)
        self.assertEqual(broken.save_dc, 11)
        self.assertLess(broken.save_total, broken.save_dc)

    def test_no_concentration_skips_save(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()

        self.manager.apply_damage(
            combat_id,
            ranger_id,
            damage_amount=12,
            source_id=wizard_id,
            rng=RandSequence([1]),
        )
        self.assertEqual(len(self.events), 1)
        self.assertIsInstance(self.events[0], DamageDealt)

    def test_zero_damage_skips_concentration_check(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()
        self._mark_and_concentrate(ranger_id, wizard_id, combat_id)

        state, _ = self.manager.apply_damage(
            combat_id,
            ranger_id,
            damage_amount=0,
            source_id=wizard_id,
        )
        self.assertEqual(
            state.combatants[ranger_id].concentration_spell_id, "hunters_mark"
        )
        self.assertEqual(len(self.events), 1)


if __name__ == "__main__":
    unittest.main()
