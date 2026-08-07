# tests/unit/test_combat_conditions.py
"""Lot C6 — conditions de combat phase 1 (frightened, poisoned)."""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import (
    ConditionApplied,
    ConditionRemoved,
)
from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, roll_d20
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.domain.combat.active_effect import ActiveEffect
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import get_connection, init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.conditions.catalog import UnknownCombatConditionError
from jdr_engine.rules.effects.collect import (
    collect_condition_roll_effects,
    collect_defender_condition_roll_effects,
)
from jdr_engine.rules.effects.registry import ActiveEffectRegistry
from jdr_engine.rules.roll_effects import roll_d20_for_combatant


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


def _wizard(*, name: str = "Mage", dex: int = 14) -> Character:
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
        hp_current=20,
        hp_max=20,
        choices={
            "spellcasting": {
                "cantrips_known": ["fire_bolt"],
                "spells_prepared": ["burning_hands", "magic_missile"],
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


def _ability_check_request(**kwargs) -> D20RollRequest:
    base = D20RollRequest(
        roll_type="ability_check",
        ability_modifier=2,
        proficiency_bonus=2,
        is_proficient=False,
        ability="wis",
    )
    return replace(base, **kwargs)


class TestConditionCollector(unittest.TestCase):
    def test_poisoned_emits_attack_and_ability_check_disadvantage(self) -> None:
        registry = ActiveEffectRegistry()
        registry.add(
            ActiveEffect(
                effect_id="poisoned",
                source_id="poisoned",
                target_id="c1",
                applied_at_round=1,
                expiry_mode="manual",
            )
        )
        effects = collect_condition_roll_effects(registry, "c1")
        self.assertEqual(len(effects), 2)
        contexts = {effect["context"] for effect in effects}
        self.assertEqual(contexts, {"attack", "ability_check"})
        self.assertTrue(all(effect["type"] == "disadvantage" for effect in effects))

    def test_frightened_emits_attack_and_ability_check_disadvantage(self) -> None:
        registry = ActiveEffectRegistry()
        registry.add(
            ActiveEffect(
                effect_id="frightened",
                source_id="frightened",
                target_id="c1",
                applied_at_round=1,
                expiry_mode="manual",
            )
        )
        effects = collect_condition_roll_effects(registry, "c1")
        self.assertEqual(len(effects), 2)
        contexts = {effect["context"] for effect in effects}
        self.assertEqual(contexts, {"attack", "ability_check"})
        self.assertTrue(all(effect["type"] == "disadvantage" for effect in effects))


class TestDefenderConditionCollector(unittest.TestCase):
    def test_poisoned_on_defender_emits_no_attack_effects_yet(self) -> None:
        """Phase 1 : seules les conditions mappées côté défenseur émettent des effets."""
        registry = ActiveEffectRegistry()
        registry.add(
            ActiveEffect(
                effect_id="poisoned",
                source_id="poisoned",
                target_id="defender",
                applied_at_round=1,
                expiry_mode="manual",
            )
        )
        effects = collect_defender_condition_roll_effects(registry, "defender")
        self.assertEqual(effects, [])

    def test_defender_id_does_not_change_attack_when_defender_has_poisoned_only(
        self,
    ) -> None:
        """``defender_id`` branché ; conditions attaquant-only sur la cible restent inertes."""
        registry = ActiveEffectRegistry()
        registry.add(
            ActiveEffect(
                effect_id="poisoned",
                source_id="poisoned",
                target_id="defender",
                applied_at_round=1,
                expiry_mode="manual",
            )
        )
        request = _attack_request()
        attacker = Combatant(
            combatant_id="attacker",
            display_name="Attaquant",
            kind="player_character",
            character_id="char-1",
            hp_current=20,
            hp_max=20,
            ac=14,
        )
        result = roll_d20_for_combatant(
            request,
            _wizard(name="Attacker"),
            attacker,
            _engine(),
            effect_registry=registry,
            defender_id="defender",
            rng=RandSequence([14]),
        )
        self.assertEqual(result.mode, "normal")
        self.assertEqual(result.kept_value, 14)


class TestD20DefenderWhenClauses(unittest.TestCase):
    """Clauses ``when`` sur advantage/disadvantage — infrastructure lot prone C6b."""

    def test_disadvantage_without_when_still_matches_all_attacks(self) -> None:
        request = _attack_request()
        effects = [
            {"type": "disadvantage", "context": "attack", "source_id": "poisoned"},
        ]
        result = roll_d20(
            D20RollContext(request=request, effects=effects),
            rng=RandSequence([18, 4]),
        )
        self.assertEqual(result.mode, "desavantage")
        self.assertEqual(result.kept_value, 4)

    def test_target_prone_melee_advantage_requires_melee_weapon_flag(self) -> None:
        request_without = _attack_request()
        request_with = _attack_request(melee_weapon=True)
        effect = {
            "type": "advantage",
            "context": "attack",
            "when": "target_prone_melee",
            "source_id": "prone",
        }
        without = roll_d20(
            D20RollContext(request=request_without, effects=[effect]),
            rng=RandSequence([10, 3]),
        )
        with_melee = roll_d20(
            D20RollContext(request=request_with, effects=[effect]),
            rng=RandSequence([10, 3]),
        )
        self.assertEqual(without.mode, "normal")
        self.assertEqual(without.kept_value, 10)
        self.assertEqual(with_melee.mode, "avantage")
        self.assertEqual(with_melee.kept_value, 10)

    def test_target_prone_ranged_disadvantage_requires_ranged_weapon_flag(self) -> None:
        request_without = _attack_request()
        request_with = _attack_request(ranged_weapon=True)
        effect = {
            "type": "disadvantage",
            "context": "attack",
            "when": "target_prone_ranged",
            "source_id": "prone",
        }
        without = roll_d20(
            D20RollContext(request=request_without, effects=[effect]),
            rng=RandSequence([18, 4]),
        )
        with_ranged = roll_d20(
            D20RollContext(request=request_with, effects=[effect]),
            rng=RandSequence([18, 4]),
        )
        self.assertEqual(without.mode, "normal")
        self.assertEqual(without.kept_value, 18)
        self.assertEqual(with_ranged.mode, "desavantage")
        self.assertEqual(with_ranged.kept_value, 4)

    def test_attacker_and_defender_prone_effects_cancel_on_melee_attack(self) -> None:
        """Attaquant prone (sans when) + cible prone mêlée (when) → annulation."""
        request = _attack_request(melee_weapon=True)
        effects = [
            {"type": "disadvantage", "context": "attack", "source_id": "prone"},
            {
                "type": "advantage",
                "context": "attack",
                "when": "target_prone_melee",
                "source_id": "prone",
            },
        ]
        result = roll_d20(
            D20RollContext(request=request, effects=effects),
            rng=RandSequence([15, 7]),
        )
        self.assertEqual(result.mode, "normal")
        self.assertEqual(len(result.rolls), 1)
        self.assertEqual(result.kept_value, 15)


class TestD20DisadvantageEffects(unittest.TestCase):
    def test_disadvantage_on_attack_from_effects(self) -> None:
        request = _attack_request()
        effects = [
            {"type": "disadvantage", "context": "attack", "source_id": "poisoned"},
        ]
        result = roll_d20(
            D20RollContext(request=request, effects=effects),
            rng=RandSequence([18, 4]),
        )
        self.assertEqual(result.mode, "desavantage")
        self.assertEqual(result.kept_value, 4)

    def test_advantage_and_disadvantage_cancel(self) -> None:
        request = _attack_request(base_mode="avantage")
        effects = [
            {"type": "disadvantage", "context": "attack", "source_id": "frightened"},
        ]
        result = roll_d20(
            D20RollContext(request=request, effects=effects),
            rng=RandSequence([18, 4]),
        )
        self.assertEqual(result.mode, "normal")
        self.assertEqual(len(result.rolls), 1)

    def test_disadvantage_does_not_affect_saving_throw(self) -> None:
        request = D20RollRequest(
            roll_type="saving_throw",
            ability_modifier=1,
            proficiency_bonus=2,
            is_proficient=False,
            ability="dex",
        )
        effects = [
            {"type": "disadvantage", "context": "attack", "source_id": "poisoned"},
        ]
        result = roll_d20(
            D20RollContext(request=request, effects=effects),
            rng=RandSequence([18, 4]),
        )
        self.assertEqual(result.mode, "normal")
        self.assertEqual(result.kept_value, 18)


class TestCombatManagerConditions(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.bus.subscribe(ConditionApplied, self.events.append)
        self.bus.subscribe(ConditionRemoved, self.events.append)
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

    def _active_fight(self) -> tuple[str, str, int]:
        state = self.manager.create_combat(
            "guild1", "channel1", [self.alice.id, self.bob.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id), rng=InitiativeSequence([10, 8])
        )
        alice_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.alice.id
        )
        bob_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.bob.id
        )
        return alice_id, bob_id, int(state.combat_id)

    def test_apply_and_remove_condition_persist(self) -> None:
        alice_id, _, combat_id = self._active_fight()
        state = self.manager.apply_condition(combat_id, alice_id, "poisoned")
        self.assertTrue(
            self.manager.query_active_effects(
                combat_id,
                effect_id="poisoned",
                target_id=alice_id,
                source_id="poisoned",
            )
        )
        self.assertIsInstance(self.events[0], ConditionApplied)

        state = self.manager.remove_condition(combat_id, alice_id, "poisoned")
        self.assertFalse(
            self.manager.query_active_effects(
                combat_id,
                effect_id="poisoned",
                target_id=alice_id,
            )
        )
        self.assertIsInstance(self.events[1], ConditionRemoved)

        reloaded = self.manager.load_combat(combat_id)
        self.assertFalse(
            self.manager.query_active_effects(
                combat_id,
                effect_id="poisoned",
                target_id=alice_id,
            )
        )

    def test_unknown_condition_rejected(self) -> None:
        alice_id, _, combat_id = self._active_fight()
        with self.assertRaises(UnknownCombatConditionError):
            self.manager.apply_condition(combat_id, alice_id, "prone")

    def test_poisoned_attack_roll_disadvantage(self) -> None:
        alice_id, bob_id, combat_id = self._active_fight()
        self.manager.apply_condition(combat_id, alice_id, "poisoned")

        resolution = self.manager.resolve_attack_roll(
            combat_id,
            alice_id,
            bob_id,
            _attack_request(),
            rng=RandSequence([17, 5]),
        )
        self.assertEqual(resolution.d20.mode, "desavantage")
        self.assertEqual(resolution.d20.kept_value, 5)

    def test_advantage_cancels_poisoned_disadvantage_on_attack(self) -> None:
        alice_id, bob_id, combat_id = self._active_fight()
        self.manager.apply_condition(combat_id, alice_id, "poisoned")

        resolution = self.manager.resolve_attack_roll(
            combat_id,
            alice_id,
            bob_id,
            _attack_request(base_mode="avantage"),
            rng=RandSequence([17, 5]),
        )
        self.assertEqual(resolution.d20.mode, "normal")
        self.assertEqual(len(resolution.d20.rolls), 1)

    def test_frightened_ability_check_disadvantage(self) -> None:
        alice_id, _, combat_id = self._active_fight()
        state = self.manager.apply_condition(combat_id, alice_id, "frightened")
        combatant = state.combatants[alice_id]
        character = self.char_repo.get_by_id(self.alice.id)
        assert character is not None

        result = roll_d20_for_combatant(
            _ability_check_request(),
            character,
            combatant,
            self.engine,
            effect_registry=self.manager.active_effect_registry(combat_id),
            rng=RandSequence([16, 6]),
        )
        self.assertEqual(result.mode, "desavantage")
        self.assertEqual(result.kept_value, 6)

    def test_poisoned_does_not_affect_saving_throw(self) -> None:
        alice_id, bob_id, combat_id = self._active_fight()
        self.manager.apply_condition(combat_id, bob_id, "poisoned")

        character = self.char_repo.get_by_id(self.bob.id)
        assert character is not None
        target = self.manager.load_combat(combat_id).combatants[bob_id]
        save_request = D20RollRequest(
            roll_type="saving_throw",
            ability_modifier=2,
            proficiency_bonus=2,
            is_proficient=False,
            ability="dex",
        )
        result = roll_d20_for_combatant(
            save_request,
            character,
            target,
            self.engine,
            effect_registry=self.manager.active_effect_registry(combat_id),
            rng=RandSequence([18, 3]),
        )
        self.assertEqual(result.mode, "normal")
        self.assertEqual(result.kept_value, 18)
        self.assertEqual(len(result.rolls), 1)

    def test_double_apply_is_idempotent(self) -> None:
        alice_id, _, combat_id = self._active_fight()
        self.manager.apply_condition(combat_id, alice_id, "poisoned")
        self.manager.apply_condition(combat_id, alice_id, "poisoned")
        self.assertEqual(len(self.events), 1)
        effects = self.manager.query_active_effects(
            combat_id,
            effect_id="poisoned",
            target_id=alice_id,
        )
        self.assertEqual(len(effects), 1)

    def test_frightened_and_poisoned_coexist_on_same_target(self) -> None:
        alice_id, _, combat_id = self._active_fight()
        self.manager.apply_condition(combat_id, alice_id, "frightened")
        self.manager.apply_condition(combat_id, alice_id, "poisoned")
        registry = self.manager.active_effect_registry(combat_id)
        effects = collect_condition_roll_effects(registry, alice_id)
        self.assertEqual(len(effects), 4)
        self.assertEqual(
            {effect["source_id"] for effect in effects},
            {"frightened", "poisoned"},
        )

    def test_legacy_conditions_blob_hydrates_registry_on_reload(self) -> None:
        alice_id, bob_id, combat_id = self._active_fight()
        record = self.combat_repo.get_by_id(combat_id)
        assert record is not None
        legacy_blob = record.state.to_dict()
        legacy_blob["active_effects"] = []
        legacy_blob["combatants"][alice_id]["conditions"] = ["poisoned"]

        payload = json.dumps(legacy_blob, ensure_ascii=False)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE combats SET state_json = ? WHERE id = ?",
                (payload, combat_id),
            )
            conn.commit()

        fresh_manager = CombatManager(
            EventBus(),
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        fresh_manager.load_combat(combat_id)
        self.assertTrue(
            fresh_manager.query_active_effects(
                combat_id,
                effect_id="poisoned",
                target_id=alice_id,
                source_id="poisoned",
            )
        )

        resolution = fresh_manager.resolve_attack_roll(
            combat_id,
            alice_id,
            bob_id,
            _attack_request(),
            rng=RandSequence([17, 5]),
        )
        self.assertEqual(resolution.d20.mode, "desavantage")

        migrated = self.combat_repo.get_state_blob(combat_id)
        assert migrated is not None
        self.assertNotIn("conditions", migrated["combatants"][alice_id])
        self.assertTrue(
            any(
                effect["effect_id"] == "poisoned"
                and effect["target_id"] == alice_id
                for effect in migrated["active_effects"]
            )
        )


if __name__ == "__main__":
    unittest.main()
