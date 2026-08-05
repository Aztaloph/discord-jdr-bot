# tests/unit/test_combat_buffs.py
"""Lot B4 — buffs combat via ActiveEffect (ADR-006 commit B)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import ConcentrationBroken, DamageDealt
from jdr_engine.dice.d20 import D20RollRequest
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.active_effect import ActiveEffect
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.spell_resolution import build_save_request
from jdr_engine.rules.roll_effects import roll_d20_for_combatant
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


def _wizard(*, name: str = "Mage", hp: int = 20) -> Character:
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


def _cleric(*, name: str = "Clerc") -> Character:
    return Character(
        owner_id="113",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="cleric",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 10,
                "dex": 10,
                "con": 12,
                "int": 10,
                "wis": 16,
                "cha": 10,
            }
        ),
        hp_current=22,
        hp_max=22,
        choices={
            "spellcasting": {
                "cantrips_known": ["sacred_flame"],
                "spells_prepared": ["bless", "burning_hands", "cure_wounds"],
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
    )
    if not kwargs:
        return base
    return D20RollRequest(
        roll_type=kwargs.get("roll_type", base.roll_type),
        ability_modifier=kwargs.get("ability_modifier", base.ability_modifier),
        proficiency_bonus=kwargs.get("proficiency_bonus", base.proficiency_bonus),
        is_proficient=kwargs.get("is_proficient", base.is_proficient),
        base_mode=kwargs.get("base_mode", base.base_mode),
    )


def _has_effect(
    manager: CombatManager,
    combat_id: int,
    *,
    effect_id: str,
    target_id: str,
    source_id: str | None = None,
) -> bool:
    effects = manager.query_active_effects(
        combat_id,
        effect_id=effect_id,
        target_id=target_id,
    )
    if source_id is None:
        return bool(effects)
    return any(effect.source_id == source_id for effect in effects)


def _bless_effect(*, source_id: str, target_id: str) -> ActiveEffect:
    return ActiveEffect(
        effect_id="blessed",
        source_id=source_id,
        target_id=target_id,
        applied_at_round=1,
        expiry_mode="concentration",
    )


class TestHuntersMarkBuff(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        init_database(self.db_path)
        self.engine = _engine()
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.char_repo = SqliteCharacterRepository(self.db_path)
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
            int(state.combat_id),
            rng=InitiativeSequence([10, 8]),
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

    def test_hunters_mark_adds_1d6_damage_when_caster_hits_marked_target(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)
        wizard_hp = self.manager.load_combat(combat_id).combatants[wizard_id].hp_current

        state, resolution = self.manager.apply_damage(
            combat_id,
            wizard_id,
            damage_amount=5,
            source_id=ranger_id,
            rng=RandSequence([4]),
        )
        self.assertEqual(resolution.application.damage_dealt, 9)
        self.assertEqual(state.combatants[wizard_id].hp_current, wizard_hp - 9)

    def test_hunters_mark_no_bonus_unmarked_target(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)

        state, resolution = self.manager.apply_damage(
            combat_id,
            ranger_id,
            damage_amount=5,
            source_id=wizard_id,
            rng=RandSequence([6]),
        )
        self.assertEqual(resolution.application.damage_dealt, 5)

    def test_hunters_mark_no_bonus_wrong_attacker(self) -> None:
        extra = _wizard(name="Charlie")
        self.char_repo.save(extra)
        state = self.manager.create_combat(
            "guild1", "channel1", [self.ranger.id, self.wizard.id, extra.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([14, 10, 6]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        ranger_id = id_map[self.ranger.id]
        wizard_id = id_map[self.wizard.id]
        charlie_id = id_map[extra.id]
        combat_id = int(state.combat_id)

        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)
        _, resolution = self.manager.apply_damage(
            combat_id,
            wizard_id,
            damage_amount=5,
            source_id=charlie_id,
            rng=RandSequence([6]),
        )
        self.assertEqual(resolution.application.damage_dealt, 5)

    def test_concentration_break_clears_hunters_mark_overlay(self) -> None:
        ranger_id, wizard_id, combat_id = self._active_fight()
        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)

        state, _ = self.manager.apply_damage(
            combat_id,
            ranger_id,
            damage_amount=22,
            source_id=wizard_id,
            rng=RandSequence([3]),
        )
        self.assertIsNone(state.combatants[ranger_id].concentration_spell_id)
        self.assertFalse(
            _has_effect(
                self.manager,
                combat_id,
                effect_id="hunters_mark",
                target_id=wizard_id,
                source_id=ranger_id,
            )
        )

    def test_recast_hunters_mark_clears_previous_target_mark(self) -> None:
        extra = _wizard(name="Charlie")
        self.char_repo.save(extra)
        state = self.manager.create_combat(
            "guild1", "channel1", [self.ranger.id, self.wizard.id, extra.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([14, 10, 6]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        ranger_id = id_map[self.ranger.id]
        wizard_id = id_map[self.wizard.id]
        charlie_id = id_map[extra.id]
        combat_id = int(state.combat_id)

        self.manager.cast_hunters_mark(combat_id, ranger_id, wizard_id)
        for _ in range(3):
            self.manager.advance_turn(combat_id)
        self.manager.cast_hunters_mark(combat_id, ranger_id, charlie_id)
        self.assertFalse(
            _has_effect(
                self.manager,
                combat_id,
                effect_id="hunters_mark",
                target_id=wizard_id,
                source_id=ranger_id,
            )
        )
        self.assertTrue(
            _has_effect(
                self.manager,
                combat_id,
                effect_id="hunters_mark",
                target_id=charlie_id,
                source_id=ranger_id,
            )
        )


class TestBlessBuff(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        init_database(self.db_path)
        self.engine = _engine()
        self.bus = EventBus()
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.cleric = _cleric(name="Clerc")
        self.ranger = _ranger(name="Alice")
        self.wizard = _wizard(name="Bob")
        for char in (self.cleric, self.ranger, self.wizard):
            self.char_repo.save(char)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _three_way_fight(self) -> tuple[str, str, str, int]:
        state = self.manager.create_combat(
            "guild1",
            "channel1",
            [self.cleric.id, self.ranger.id, self.wizard.id],
        )
        state = self.manager.activate_combat(
            int(state.combat_id),
            rng=InitiativeSequence([16, 12, 8]),
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        return (
            id_map[self.cleric.id],
            id_map[self.ranger.id],
            id_map[self.wizard.id],
            int(state.combat_id),
        )

    def test_bless_adds_1d4_to_attack_roll(self) -> None:
        cleric_id, ranger_id, wizard_id, combat_id = self._three_way_fight()
        self.manager.cast_bless(combat_id, cleric_id, [ranger_id])
        self.manager.advance_turn(combat_id)

        resolution = self.manager.resolve_attack_roll(
            combat_id,
            ranger_id,
            wizard_id,
            _attack_request(),
            rng=RandSequence([11, 3]),
        )
        self.assertEqual(resolution.d20.total, 11 + 5 + 2 + 3)
        self.assertTrue(
            any("+3 (bless)" in entry for entry in resolution.d20.applied_effects)
        )

    def test_bless_adds_1d4_to_saving_throw(self) -> None:
        combatant = Combatant(
            combatant_id="wiz",
            display_name="Bob",
            kind="player_character",
            character_id=self.wizard.id,
            hp_current=20,
            hp_max=20,
            ac=12,
        )
        request = build_save_request(self.wizard, self.engine, "dex")
        bless = _bless_effect(source_id="cleric", target_id="wiz")
        result = roll_d20_for_combatant(
            request,
            self.wizard,
            combatant,
            self.engine,
            active_effects=(bless,),
            rng=RandSequence([9, 2]),
        )
        self.assertIn("+2 (bless)", result.applied_effects)

    def test_bless_three_targets_independent_rolls(self) -> None:
        char = self.ranger
        for expected_bonus in (2, 3, 4):
            combatant = Combatant(
                combatant_id=f"t{expected_bonus}",
                display_name="Cible",
                kind="player_character",
                character_id=char.id,
                hp_current=20,
                hp_max=20,
                ac=12,
            )
            bless = _bless_effect(
                source_id="cleric",
                target_id=combatant.combatant_id,
            )
            result = roll_d20_for_combatant(
                _attack_request(),
                char,
                combatant,
                self.engine,
                active_effects=(bless,),
                rng=RandSequence([10, expected_bonus]),
            )
            self.assertIn(f"+{expected_bonus} (bless)", result.applied_effects)

    def test_concentration_break_clears_blessed_on_all_targets(self) -> None:
        cleric_id, ranger_id, wizard_id, combat_id = self._three_way_fight()
        self.manager.cast_bless(combat_id, cleric_id, [ranger_id, wizard_id])
        state, _ = self.manager.apply_damage(
            combat_id,
            cleric_id,
            damage_amount=24,
            source_id=wizard_id,
            rng=RandSequence([2]),
        )
        self.assertIsNone(state.combatants[cleric_id].concentration_spell_id)
        self.assertFalse(
            _has_effect(
                self.manager,
                combat_id,
                effect_id="blessed",
                target_id=ranger_id,
                source_id=cleric_id,
            )
        )
        self.assertFalse(
            _has_effect(
                self.manager,
                combat_id,
                effect_id="blessed",
                target_id=wizard_id,
                source_id=cleric_id,
            )
        )


if __name__ == "__main__":
    unittest.main()
