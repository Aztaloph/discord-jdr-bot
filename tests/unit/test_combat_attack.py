# tests/unit/test_combat_attack.py
"""Lot C3a — jet d'attaque, dégâts, overlay PV combat."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import AttackRollResolved, DamageDealt
from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, D20RollResult, roll_d20
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.attack_roll import resolve_attack_hit
from jdr_engine.rules.combat.damage import (
    apply_damage_to_hp,
    roll_damage,
)


class RandSequence:
    """RNG injectable pour ``randint(a, b)``."""

    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self, a: int, b: int) -> int:
        if not self._values:
            raise RuntimeError("RandSequence épuisé")
        return self._values.pop(0)


class InitiativeSequence:
    """RNG injectable pour l'initiative (``() -> int``)."""

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


def _wizard(
    engine: RuleEngine,
    *,
    name: str = "Test Mage",
    dex: int = 14,
    hp: int = 20,
) -> Character:
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


def _attack_request(**kwargs) -> D20RollRequest:
    base = D20RollRequest(
        roll_type="attack",
        ability_modifier=5,
        proficiency_bonus=2,
        is_proficient=True,
        ability="dex",
    )
    return replace(base, **kwargs)


class TestAttackHitRules(unittest.TestCase):
    def _d20(self, kept: int, *, total_mod: int = 5) -> D20RollResult:
        req = _attack_request()
        return D20RollResult(
            request=req,
            rolls=[kept],
            is_kept=[True],
            kept_value=kept,
            mode="normal",
            modifier=total_mod,
            modifier_breakdown="+5",
            total=kept + total_mod,
            natural_20=kept == 20,
            natural_1=kept == 1,
        )

    def test_hit_when_total_meets_ac(self) -> None:
        outcome = resolve_attack_hit(self._d20(12), target_ac=17)
        self.assertTrue(outcome.hit)
        self.assertFalse(outcome.critical)
        self.assertFalse(outcome.automatic_miss)

    def test_miss_when_below_ac(self) -> None:
        outcome = resolve_attack_hit(self._d20(8), target_ac=17)
        self.assertFalse(outcome.hit)

    def test_natural_20_hits_and_crits(self) -> None:
        outcome = resolve_attack_hit(self._d20(20), target_ac=30)
        self.assertTrue(outcome.hit)
        self.assertTrue(outcome.critical)
        self.assertFalse(outcome.automatic_miss)

    def test_natural_1_automatic_miss(self) -> None:
        outcome = resolve_attack_hit(self._d20(1), target_ac=5)
        self.assertFalse(outcome.hit)
        self.assertTrue(outcome.automatic_miss)

    def test_advantage_uses_d20_engine(self) -> None:
        req = _attack_request(base_mode="avantage")
        result = roll_d20(
            D20RollContext(request=req),
            rng=RandSequence([4, 18]),
        )
        self.assertEqual(result.kept_value, 18)
        self.assertEqual(result.mode, "avantage")


class TestDamageRules(unittest.TestCase):
    def test_apply_damage_floors_at_zero(self) -> None:
        app = apply_damage_to_hp(7, 15)
        self.assertEqual(app.hp_after, 0)
        self.assertEqual(app.damage_dealt, 7)

    def test_crit_doubles_dice_not_modifier(self) -> None:
        result = roll_damage("1d8+3", critical=True, rng=RandSequence([4, 6]))
        self.assertEqual(result.rolls, (4, 6))
        self.assertEqual(result.total, 13)
        self.assertTrue(result.critical)


class TestCombatManagerAttack(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.bus.subscribe(AttackRollResolved, self.events.append)
        self.bus.subscribe(DamageDealt, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.alice = _wizard(self.engine, name="Alice", dex=16)
        self.bob = _wizard(self.engine, name="Bob", dex=10, hp=30)
        self.char_repo.save(self.alice)
        self.char_repo.save(self.bob)
        self.bob_hp_before = self.bob.hp_current

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _active_fight(self) -> tuple[str, str, int]:
        state = self.manager.create_combat(
            "guild1", "channel1", [self.alice.id, self.bob.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id), rng=InitiativeSequence([10, 8])
        )
        alice_id = next(
            cid for cid, c in state.combatants.items() if c.character_id == self.alice.id
        )
        bob_id = next(
            cid for cid, c in state.combatants.items() if c.character_id == self.bob.id
        )
        return alice_id, bob_id, int(state.combat_id)

    def test_attack_roll_hit_and_miss(self) -> None:
        alice_id, bob_id, combat_id = self._active_fight()
        bob = self.manager.load_combat(combat_id).combatants[bob_id]

        hit = self.manager.resolve_attack_roll(
            combat_id,
            alice_id,
            bob_id,
            _attack_request(),
            rng=RandSequence([14]),
        )
        self.assertTrue(hit.outcome.hit)
        self.assertIsInstance(self.events[0], AttackRollResolved)

        loaded = self.manager.load_combat(combat_id)
        self.assertEqual(loaded.combatants[bob_id].hp_current, bob.hp_current)

    def test_attack_roll_natural_1_miss(self) -> None:
        alice_id, bob_id, combat_id = self._active_fight()
        miss = self.manager.resolve_attack_roll(
            combat_id,
            alice_id,
            bob_id,
            _attack_request(),
            rng=RandSequence([1]),
        )
        self.assertTrue(miss.outcome.automatic_miss)

    def test_apply_damage_updates_combat_not_character(self) -> None:
        alice_id, bob_id, combat_id = self._active_fight()
        bob_hp = self.manager.load_combat(combat_id).combatants[bob_id].hp_current

        state, resolution = self.manager.apply_damage(
            combat_id,
            bob_id,
            "2d6+3",
            source_id=alice_id,
            rng=RandSequence([4, 5]),
        )
        self.assertEqual(resolution.roll.total, 12)
        self.assertEqual(state.combatants[bob_id].hp_current, bob_hp - 12)
        self.assertIsInstance(self.events[-1], DamageDealt)

        reloaded = self.manager.load_combat(combat_id)
        self.assertEqual(reloaded.combatants[bob_id].hp_current, bob_hp - 12)

        persisted_bob = self.char_repo.get_by_id(self.bob.id)
        assert persisted_bob is not None
        self.assertEqual(persisted_bob.hp_current, self.bob_hp_before)

    def test_crit_damage_doubles_dice_only(self) -> None:
        _, bob_id, combat_id = self._active_fight()
        bob_hp = self.manager.load_combat(combat_id).combatants[bob_id].hp_current

        _, resolution = self.manager.apply_damage(
            combat_id,
            bob_id,
            "1d8+3",
            critical=True,
            rng=RandSequence([3, 5]),
        )
        self.assertEqual(resolution.roll.total, 11)
        loaded = self.manager.load_combat(combat_id)
        self.assertEqual(loaded.combatants[bob_id].hp_current, bob_hp - 11)

    def test_damage_cannot_go_below_zero(self) -> None:
        _, bob_id, combat_id = self._active_fight()
        state, resolution = self.manager.apply_damage(
            combat_id,
            bob_id,
            "10d6",
            rng=RandSequence([6] * 10),
        )
        self.assertEqual(resolution.application.hp_after, 0)
        self.assertEqual(state.combatants[bob_id].hp_current, 0)


if __name__ == "__main__":
    unittest.main()
