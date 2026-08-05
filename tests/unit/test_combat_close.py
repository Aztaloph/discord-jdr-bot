# tests/unit/test_combat_close.py
"""Lot ADR-005 — transition fin de rencontre (clôture, sync fiche, auto-close)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import CombatEnded, TurnEnded
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.concentration import (
    get_active_concentration,
    set_concentration,
)
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


def _wizard(*, name: str = "Mage", dex: int = 14, hp: int = 20) -> Character:
    return Character(
        owner_id="111",
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


def _ranger(*, name: str = "Rodeur") -> Character:
    return Character(
        owner_id="112",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="ranger",
        level=2,
        ability_scores=AbilityScores(
            scores={
                "str": 12,
                "dex": 16,
                "con": 12,
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


class TestCombatClose(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        init_database(self.db_path)
        self.engine = _engine()
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.char_repo = SqliteCharacterRepository(self.db_path)
        for event_type in (CombatEnded, TurnEnded):
            self.bus.subscribe(event_type, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.alice = _wizard(name="Alice", dex=16)
        self.bob = _wizard(name="Bob", dex=10)
        self.char_repo.save(self.alice)
        self.char_repo.save(self.bob)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _activate_two(self) -> tuple[CombatState, str, str, int]:
        state = self.manager.create_combat(
            "guild1", "channel1", [self.alice.id, self.bob.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([15, 10]),
        )
        alice_id = next(
            cid for cid, c in state.combatants.items() if c.character_id == self.alice.id
        )
        bob_id = next(
            cid for cid, c in state.combatants.items() if c.character_id == self.bob.id
        )
        return state, alice_id, bob_id, int(state.combat_id)

    def test_advance_turn_auto_closes_when_no_active_combatants(self) -> None:
        state, alice_id, bob_id, combat_id = self._activate_two()
        self.manager.remove_combatant(combat_id, alice_id)
        self.manager.remove_combatant(combat_id, bob_id)
        closed = self.manager.advance_turn(combat_id)
        self.assertEqual(closed.status, "ended")
        self.assertEqual(
            [e for e in self.events if isinstance(e, CombatEnded)][-1].reason,
            "no_active_combatants",
        )

    def test_advance_turn_auto_closes_when_all_at_zero_hp(self) -> None:
        state, alice_id, bob_id, combat_id = self._activate_two()
        self.manager.apply_damage(
            combat_id, alice_id, damage_amount=20, source_id=bob_id
        )
        self.manager.apply_damage(
            combat_id, bob_id, damage_amount=20, source_id=alice_id
        )
        closed = self.manager.advance_turn(combat_id)
        self.assertEqual(closed.status, "ended")
        self.assertEqual(
            [e for e in self.events if isinstance(e, CombatEnded)][-1].reason,
            "no_active_combatants",
        )

    def test_advance_turn_continues_with_single_active_combatant(self) -> None:
        state, alice_id, bob_id, combat_id = self._activate_two()
        order = state.initiative_order
        self.manager.remove_combatant(combat_id, alice_id)
        advanced = self.manager.advance_turn(combat_id)
        self.assertEqual(advanced.status, "active")
        self.assertEqual(advanced.initiative_order[advanced.turn_index], order[1])

    def test_apply_damage_sets_inactive_at_zero_hp(self) -> None:
        _, _, bob_id, combat_id = self._activate_two()
        state, _ = self.manager.apply_damage(
            combat_id,
            bob_id,
            "10d6",
            rng=RandSequence([6] * 10),
        )
        self.assertEqual(state.combatants[bob_id].hp_current, 0)
        self.assertFalse(state.combatants[bob_id].is_active)

    def test_close_combat_syncs_hp_to_character(self) -> None:
        _, _, bob_id, combat_id = self._activate_two()
        bob_hp_before = self.bob.hp_current
        self.manager.apply_damage(
            combat_id, bob_id, damage_amount=7, source_id=bob_id
        )
        self.manager.close_combat(combat_id, reason="test")
        reloaded = self.char_repo.get_by_id(self.bob.id)
        assert reloaded is not None
        self.assertEqual(reloaded.hp_current, bob_hp_before - 7)

    def test_close_combat_does_not_sync_hp_max_or_ac(self) -> None:
        _, _, bob_id, combat_id = self._activate_two()
        bob_max = self.bob.hp_max
        self.manager.apply_damage(
            combat_id, bob_id, damage_amount=5, source_id=bob_id
        )
        self.manager.close_combat(combat_id)
        reloaded = self.char_repo.get_by_id(self.bob.id)
        assert reloaded is not None
        self.assertEqual(reloaded.hp_max, bob_max)

    def test_close_combat_idempotent(self) -> None:
        _, _, _, combat_id = self._activate_two()
        self.manager.close_combat(combat_id, reason="first")
        ended_count = len([e for e in self.events if isinstance(e, CombatEnded)])
        closed_again = self.manager.close_combat(combat_id, reason="second")
        self.assertEqual(closed_again.status, "ended")
        self.assertEqual(
            len([e for e in self.events if isinstance(e, CombatEnded)]),
            ended_count,
        )

    def test_close_combat_conditions_stay_overlay_only_not_on_character(
        self,
    ) -> None:
        _, _, bob_id, combat_id = self._activate_two()
        self.manager.apply_condition(combat_id, bob_id, "poisoned")
        closed = self.manager.close_combat(combat_id)
        self.assertIn("poisoned", closed.combatants[bob_id].conditions)
        reloaded = self.char_repo.get_by_id(self.bob.id)
        assert reloaded is not None
        spellcasting = get_spellcasting_state(reloaded)
        self.assertNotIn("conditions", spellcasting)
        self.assertNotIn("conditions", reloaded.choices or {})

    def test_close_combat_reconciles_concentration_overlay_to_choices(self) -> None:
        ranger = _ranger()
        target = _wizard(name="Cible", hp=18)
        self.char_repo.save(ranger)
        self.char_repo.save(target)
        state = self.manager.create_combat(
            "guild1", "channel1", [ranger.id, target.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([14, 8]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        caster_id = id_map[ranger.id]
        target_id = id_map[target.id]
        self.manager.cast_hunters_mark(int(state.combat_id), caster_id, target_id)
        self.manager.close_combat(int(state.combat_id))
        reloaded = self.char_repo.get_by_id(ranger.id)
        assert reloaded is not None
        conc = get_active_concentration(reloaded)
        assert conc is not None
        self.assertEqual(conc["spell_id"], "hunters_mark")

    def test_load_combat_hydrates_concentration_from_character_when_overlay_missing(
        self,
    ) -> None:
        ranger = _ranger()
        ranger, _ = set_concentration(ranger, "hunters_mark", "Hunter's Mark")
        dummy = _wizard(name="Dummy", hp=20)
        self.char_repo.save(ranger)
        self.char_repo.save(dummy)
        state = self.manager.create_combat(
            "guild1", "channel1", [ranger.id, dummy.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([12, 8]),
        )
        combat_id = int(state.combat_id)
        ranger_cid = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == ranger.id
        )
        raw = self.manager.load_combat(combat_id)
        self.assertEqual(
            raw.combatants[ranger_cid].concentration_spell_id,
            "hunters_mark",
        )

    def test_auto_close_publishes_combat_ended_with_reason(self) -> None:
        state, alice_id, bob_id, combat_id = self._activate_two()
        self.manager.remove_combatant(combat_id, alice_id)
        self.manager.remove_combatant(combat_id, bob_id)
        self.events.clear()
        self.manager.advance_turn(combat_id)
        ended = [e for e in self.events if isinstance(e, CombatEnded)]
        self.assertEqual(len(ended), 1)
        self.assertEqual(ended[0].reason, "no_active_combatants")


if __name__ == "__main__":
    unittest.main()
