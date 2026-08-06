# tests/unit/test_hex_combat.py
"""Lot B4e — maléfice (hex) : bonus dégâts de sort uniquement."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import EventBus
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine


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


def _warlock(*, name: str = "Occultiste", con: int = 12) -> Character:
    return Character(
        owner_id="201",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="warlock",
        level=2,
        ability_scores=AbilityScores(
            scores={
                "str": 8,
                "dex": 14,
                "con": con,
                "int": 10,
                "wis": 10,
                "cha": 16,
            }
        ),
        hp_current=20,
        hp_max=20,
        choices={
            "spellcasting": {
                "spells_known": ["hex"],
                "cantrips_known": ["eldritch_blast"],
                "slots_used": {},
            }
        },
    )


def _wizard(*, name: str = "Mage", hp: int = 30) -> Character:
    return Character(
        owner_id="202",
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
        hp_current=hp,
        hp_max=hp,
        choices={
            "spellcasting": {
                "cantrips_known": ["fire_bolt"],
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            }
        },
    )


def _has_hex(
    manager: CombatManager,
    combat_id: int,
    *,
    target_id: str,
    source_id: str,
) -> bool:
    effects = manager.query_active_effects(
        combat_id,
        effect_id="hexed",
        target_id=target_id,
        source_id=source_id,
    )
    return bool(effects)


class TestHexCombat(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        init_database(self.db_path)
        self.engine = _engine()
        self.manager = CombatManager(
            EventBus(),
            SqliteCombatRepository(self.db_path),
            SqliteCharacterRepository(self.db_path),
            self.engine,
        )
        self.warlock = _warlock(name="Alice")
        self.wizard = _wizard(name="Bob")
        self.char_repo = self.manager._characters
        self.char_repo.save(self.warlock)
        self.char_repo.save(self.wizard)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _active_fight(self) -> tuple[str, str, int]:
        state = self.manager.create_combat(
            "guild1", "channel1", [self.warlock.id, self.wizard.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([16, 8]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        return id_map[self.warlock.id], id_map[self.wizard.id], int(state.combat_id)

    def test_hex_adds_1d6_on_spell_damage_path(self) -> None:
        warlock_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hex(combat_id, warlock_id, wizard_id)
        wizard_hp = self.manager.load_combat(combat_id).combatants[wizard_id].hp_current

        state, resolution = self.manager.apply_damage(
            combat_id,
            wizard_id,
            damage_amount=4,
            source_id=warlock_id,
            spell_damage=True,
            rng=RandSequence([5]),
        )
        self.assertEqual(resolution.application.damage_dealt, 9)
        self.assertEqual(state.combatants[wizard_id].hp_current, wizard_hp - 9)

    def test_hex_no_bonus_on_generic_damage(self) -> None:
        warlock_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hex(combat_id, warlock_id, wizard_id)

        _, resolution = self.manager.apply_damage(
            combat_id,
            wizard_id,
            damage_amount=4,
            source_id=warlock_id,
            rng=RandSequence([6]),
        )
        self.assertEqual(resolution.application.damage_dealt, 4)

    def test_hex_no_bonus_wrong_attacker(self) -> None:
        extra = _wizard(name="Charlie")
        self.char_repo.save(extra)
        state = self.manager.create_combat(
            "guild1", "channel1", [self.warlock.id, self.wizard.id, extra.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([18, 12, 6]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        warlock_id = id_map[self.warlock.id]
        wizard_id = id_map[self.wizard.id]
        charlie_id = id_map[extra.id]
        combat_id = int(state.combat_id)

        self.manager.cast_hex(combat_id, warlock_id, wizard_id)
        _, resolution = self.manager.apply_damage(
            combat_id,
            wizard_id,
            damage_amount=4,
            source_id=charlie_id,
            spell_damage=True,
            rng=RandSequence([6]),
        )
        self.assertEqual(resolution.application.damage_dealt, 4)

    def test_cast_spell_attack_applies_hex_bonus(self) -> None:
        warlock_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hex(combat_id, warlock_id, wizard_id)
        self.manager.advance_turn(combat_id)
        self.manager.advance_turn(combat_id)

        hp_before = self.manager.load_combat(combat_id).combatants[wizard_id].hp_current
        state, outcome = self.manager.cast_spell_attack(
            combat_id,
            warlock_id,
            wizard_id,
            "eldritch_blast",
            rng=RandSequence([15, 4, 3]),
        )
        assert outcome.damage is not None
        self.assertEqual(outcome.damage.application.damage_dealt, 7)
        self.assertEqual(state.combatants[wizard_id].hp_current, hp_before - 7)

    def test_concentration_break_clears_hex(self) -> None:
        warlock_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hex(combat_id, warlock_id, wizard_id)

        state, _ = self.manager.apply_damage(
            combat_id,
            warlock_id,
            damage_amount=22,
            source_id=wizard_id,
            rng=RandSequence([2]),
        )
        self.assertIsNone(state.combatants[warlock_id].concentration_spell_id)
        self.assertFalse(
            _has_hex(
                self.manager,
                combat_id,
                target_id=wizard_id,
                source_id=warlock_id,
            )
        )

    def test_recast_hex_clears_previous_target(self) -> None:
        extra = _wizard(name="Charlie")
        self.char_repo.save(extra)
        state = self.manager.create_combat(
            "guild1", "channel1", [self.warlock.id, self.wizard.id, extra.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([18, 12, 6]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        warlock_id = id_map[self.warlock.id]
        wizard_id = id_map[self.wizard.id]
        charlie_id = id_map[extra.id]
        combat_id = int(state.combat_id)

        self.manager.cast_hex(combat_id, warlock_id, wizard_id)
        for _ in range(3):
            self.manager.advance_turn(combat_id)
        self.manager.cast_hex(combat_id, warlock_id, charlie_id)

        self.assertFalse(
            _has_hex(
                self.manager,
                combat_id,
                target_id=wizard_id,
                source_id=warlock_id,
            )
        )
        self.assertTrue(
            _has_hex(
                self.manager,
                combat_id,
                target_id=charlie_id,
                source_id=warlock_id,
            )
        )

    def test_hex_persists_in_blob(self) -> None:
        warlock_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hex(combat_id, warlock_id, wizard_id)

        loaded = self.manager.load_combat(combat_id)
        self.assertEqual(
            loaded.combatants[warlock_id].concentration_spell_id, "hex"
        )
        self.assertTrue(
            any(
                effect.effect_id == "hexed"
                and effect.source_id == warlock_id
                and effect.target_id == wizard_id
                for effect in loaded.active_effects
            )
        )


if __name__ == "__main__":
    unittest.main()
