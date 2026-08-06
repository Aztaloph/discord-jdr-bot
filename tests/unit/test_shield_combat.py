# tests/unit/test_shield_combat.py
"""Lot B4f — bouclier : horloge ``rounds`` (banc de test, sans +5 CA)."""
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


def _wizard(*, owner_id: str, name: str, dex: int) -> Character:
    return Character(
        owner_id=owner_id,
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="wizard",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 8,
                "dex": dex,
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
                "spells_prepared": ["shield"],
                "slots_used": {},
            }
        },
    )


def _has_shield(
    manager: CombatManager,
    combat_id: int,
    combatant_id: str,
) -> bool:
    effects = manager.query_active_effects(
        combat_id,
        effect_id="shielded",
        source_id=combatant_id,
        target_id=combatant_id,
    )
    return bool(effects)


class TestShieldCombat(unittest.TestCase):
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
        self.alice = _wizard(owner_id="101", name="Alice", dex=16)
        self.bob = _wizard(owner_id="102", name="Bob", dex=10)
        self.char_repo = self.manager._characters
        self.char_repo.save(self.alice)
        self.char_repo.save(self.bob)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _active_fight(self) -> tuple[str, str, int]:
        state = self.manager.create_combat(
            "guild1", "channel1", [self.alice.id, self.bob.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([15, 9]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        return id_map[self.alice.id], id_map[self.bob.id], int(state.combat_id)

    def test_shield_survives_intra_round_then_expires_at_next_round(self) -> None:
        alice_id, bob_id, combat_id = self._active_fight()
        state = self.manager.load_combat(combat_id)
        self.assertEqual(state.round_number, 1)
        self.assertEqual(state.initiative_order[state.turn_index], alice_id)

        self.manager.cast_shield(combat_id, alice_id)
        self.assertTrue(_has_shield(self.manager, combat_id, alice_id))

        after_intra = self.manager.advance_turn(combat_id)
        self.assertEqual(after_intra.round_number, 1)
        self.assertEqual(after_intra.initiative_order[after_intra.turn_index], bob_id)
        self.assertTrue(_has_shield(self.manager, combat_id, alice_id))

        after_round = self.manager.advance_turn(combat_id)
        self.assertEqual(after_round.round_number, 2)
        self.assertEqual(
            after_round.initiative_order[after_round.turn_index], alice_id
        )
        self.assertFalse(_has_shield(self.manager, combat_id, alice_id))

    def test_shield_persists_in_blob_until_expiry(self) -> None:
        alice_id, _bob_id, combat_id = self._active_fight()
        self.manager.cast_shield(combat_id, alice_id)

        loaded = self.manager.load_combat(combat_id)
        self.assertTrue(
            any(
                effect.effect_id == "shielded"
                and effect.source_id == alice_id
                and effect.target_id == alice_id
                and effect.expiry_mode == "rounds"
                and effect.duration_rounds == 1
                and effect.applied_at_round == 1
                for effect in loaded.active_effects
            )
        )

        self.manager.advance_turn(combat_id)
        still_round_one = self.manager.load_combat(combat_id)
        self.assertEqual(still_round_one.round_number, 1)
        self.assertTrue(_has_shield(self.manager, combat_id, alice_id))

        self.manager.advance_turn(combat_id)
        reloaded = self.manager.load_combat(combat_id)
        self.assertEqual(reloaded.round_number, 2)
        self.assertFalse(
            any(
                effect.effect_id == "shielded" and effect.source_id == alice_id
                for effect in reloaded.active_effects
            )
        )


if __name__ == "__main__":
    unittest.main()
