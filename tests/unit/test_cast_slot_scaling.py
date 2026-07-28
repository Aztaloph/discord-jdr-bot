# tests/unit/test_cast_slot_scaling.py
"""Upcast unifié — resolve_slot_scaling_increments + cast_spell (Lot slot_scaling)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.cast import (
    build_spell_display_lines,
    cast_spell,
    resolve_slot_scaling_increments,
)
from jdr_engine.rules.spellcasting.mechanics_display import format_slot_scaling_summary


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


PERIMETER_SPELL_IDS: frozenset[str] = frozenset(
    {
        "magic_missile",
        "scorching_ray",
        "burning_hands",
        "fireball",
        "lightning_bolt",
        "flaming_sphere",
        "hellish_rebuke",
        "inflict_wounds",
        "chromatic_orb",
        "spiritual_weapon",
        "cure_wounds",
        "healing_word",
    }
)


class TestResolveSlotScalingIncrements(unittest.TestCase):
    def test_delta_zero_no_increment(self):
        scaling = {"per_slot_above_base": {"missiles": 1, "damage_dice": "1d6"}}
        result = resolve_slot_scaling_increments(
            scaling, spell_base_level=1, slot_consumed_level=1
        )
        self.assertEqual(result.extra_missiles, 0)
        self.assertIsNone(result.extra_damage_dice)
        self.assertIsNone(result.extra_healing_dice)

    def test_delta_one_missiles(self):
        scaling = {"per_slot_above_base": {"missiles": 1}}
        result = resolve_slot_scaling_increments(
            scaling, spell_base_level=1, slot_consumed_level=2
        )
        self.assertEqual(result.extra_missiles, 1)
        self.assertIsNone(result.extra_damage_dice)

    def test_delta_three_damage_dice(self):
        scaling = {"per_slot_above_base": {"damage_dice": "1d6"}}
        result = resolve_slot_scaling_increments(
            scaling, spell_base_level=3, slot_consumed_level=6
        )
        self.assertEqual(result.extra_missiles, 0)
        self.assertEqual(result.extra_damage_dice, "3d6")

    def test_absent_metadata(self):
        result = resolve_slot_scaling_increments(
            None, spell_base_level=1, slot_consumed_level=3
        )
        self.assertEqual(result.extra_missiles, 0)
        self.assertIsNone(result.extra_damage_dice)
        self.assertIsNone(result.extra_healing_dice)

    def test_null_slot_scaling(self):
        result = resolve_slot_scaling_increments(
            None, spell_base_level=2, slot_consumed_level=4
        )
        self.assertEqual(result.extra_missiles, 0)

    def test_healing_dice_isolated(self):
        scaling = {"per_slot_above_base": {"healing_dice": "1d8"}}
        result = resolve_slot_scaling_increments(
            scaling, spell_base_level=1, slot_consumed_level=3
        )
        self.assertEqual(result.extra_healing_dice, "2d8")
        self.assertIsNone(result.extra_damage_dice)
        self.assertEqual(result.extra_missiles, 0)

    def test_cantrip_level_ignored(self):
        scaling = {"per_slot_above_base": {"missiles": 1}}
        result = resolve_slot_scaling_increments(
            scaling, spell_base_level=0, slot_consumed_level=3
        )
        self.assertEqual(result.extra_missiles, 0)


class TestCastSpellSlotScalingIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def _wizard(
        self,
        level: int,
        *,
        prepared: list[str],
        slots_used: dict | None = None,
        int_score: int = 16,
    ) -> Character:
        scores = dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
        scores["int"] = int_score
        return Character(
            owner_id="1",
            name="Merlin",
            race_id="human",
            class_id="wizard",
            level=level,
            ability_scores=AbilityScores(scores=scores),
            choices={
                "spellcasting": {
                    "cantrips_known": ["fire_bolt"],
                    "spells_prepared": prepared,
                    "slots_used": {
                        str(k): v for k, v in (slots_used or {}).items()
                    },
                }
            },
        )

    def _cleric(
        self,
        level: int,
        *,
        prepared: list[str],
        slots_used: dict | None = None,
        wis_score: int = 16,
        hp_current: int = 10,
    ) -> Character:
        scores = dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
        scores["wis"] = wis_score
        char = Character(
            owner_id="1",
            name="Marie",
            race_id="human",
            class_id="cleric",
            level=level,
            ability_scores=AbilityScores(scores=scores),
            hp_current=hp_current,
            choices={
                "spellcasting": {
                    "cantrips_known": ["sacred_flame"],
                    "spells_prepared": prepared,
                    "slots_used": {
                        str(k): v for k, v in (slots_used or {}).items()
                    },
                }
            },
        )
        char.hp_max = 40
        return char

    def test_magic_missile_slot_3_five_darts(self):
        char = self._wizard(
            5,
            prepared=["magic_missile"],
            slots_used={1: 4, 2: 3},
        )
        rng = SequenceRng([1, 2, 3, 4, 5])
        result = cast_spell(
            char, "magic_missile", self.engine, rng=rng, persist_slots=False
        )
        self.assertEqual(result.slot_consumed_level, 3)
        self.assertEqual(len(result.attack_rolls), 5)
        self.assertEqual(result.damage_total, 20)  # (1+1)+(2+1)+(3+1)+(4+1)+(5+1)

    def test_fireball_slot_5_ten_d6(self):
        char = self._wizard(
            9,
            prepared=["fireball"],
            slots_used={1: 4, 2: 3, 3: 3, 4: 3},
        )
        rng = SequenceRng([6] * 10)
        result = cast_spell(
            char, "fireball", self.engine, rng=rng, persist_slots=False
        )
        self.assertEqual(result.slot_consumed_level, 5)
        self.assertEqual(result.damage_total, 60)
        self.assertIn("8d6 + 2d6", result.damage_notation or "")

    def test_cure_wounds_slot_3_three_d8_plus_mod_once(self):
        char = self._cleric(
            5,
            prepared=["cure_wounds"],
            slots_used={1: 4, 2: 3},
        )
        rng = SequenceRng([4, 5, 6])
        result = cast_spell(
            char, "cure_wounds", self.engine, rng=rng, persist_slots=False
        )
        self.assertEqual(result.slot_consumed_level, 3)
        self.assertEqual(result.healing_total, 18)  # 4+5+6 + mod SAG +3
        self.assertIn("1d8 + 2d8", result.damage_notation or "")

    def test_spiritual_weapon_slot_4_three_d8_plus_mod(self):
        char = self._cleric(
            7,
            prepared=["spiritual_weapon"],
            slots_used={1: 4, 2: 3, 3: 3},
        )
        rng = SequenceRng([12, 6, 7, 8])
        result = cast_spell(
            char, "spiritual_weapon", self.engine, rng=rng, persist_slots=False
        )
        self.assertEqual(result.slot_consumed_level, 4)
        # Total calculé (pas la notation) : base 1d8=6 + incrément 2d8=7+8 + mod +3
        self.assertEqual(result.damage_rolls, [6, 7, 8])
        self.assertEqual(result.attack_rolls[0].damage_total, 6)
        self.assertEqual(result.damage_total, 24)
        self.assertIn("1d8 + 2d8", result.damage_notation or "")

    def test_flaming_sphere_slot_4_base_2d6_plus_increment_2d6(self):
        """Cas piège : base (2d6) ≠ incrément (1d6) — les deux doivent entrer dans le total."""
        char = self._wizard(
            7,
            prepared=["flaming_sphere"],
            slots_used={1: 4, 2: 3, 3: 3},
        )
        rng = SequenceRng([3, 3, 3, 3])
        result = cast_spell(
            char, "flaming_sphere", self.engine, rng=rng, persist_slots=False
        )
        self.assertEqual(result.slot_consumed_level, 4)
        self.assertEqual(result.effect_type, "saving_throw")
        self.assertEqual(result.damage_rolls, [3, 3, 3, 3])
        self.assertEqual(result.damage_total, 12)
        self.assertIn("2d6 + 2d6", result.damage_notation or "")

    def test_healing_word_slot_3_three_d4_plus_mod_once(self):
        char = Character(
            owner_id="1",
            name="Bard",
            race_id="human",
            class_id="bard",
            level=5,
            ability_scores=AbilityScores(
                scores=dict.fromkeys(
                    ("str", "dex", "con", "int", "wis", "cha"), 10
                )
                | {"cha": 16}
            ),
            hp_current=10,
            choices={
                "spellcasting": {
                    "cantrips_known": ["vicious_mockery"],
                    "spells_known": ["healing_word"],
                    "slots_used": {"1": 4, "2": 3},
                }
            },
        )
        char.hp_max = 40
        rng = SequenceRng([2, 3, 4])
        result = cast_spell(
            char, "healing_word", self.engine, rng=rng, persist_slots=False
        )
        self.assertEqual(result.slot_consumed_level, 3)
        self.assertEqual(result.healing_rolls, [2, 3, 4])
        self.assertEqual(result.healing_total, 12)  # 2+3+4 + mod CHA +3, une seule fois


class TestCastSlotScalingDisplayConcordance(unittest.TestCase):
    """Embed (mechanics_display) et cast concordent pour les sorts du périmètre."""

    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_perimeter_spells_have_slot_scaling_metadata(self):
        for spell_id in PERIMETER_SPELL_IDS:
            with self.subTest(spell_id=spell_id):
                entry = self.engine.get_entity("spell", spell_id)
                self.assertIsNotNone(entry)
                mechanics = entry.definition.mechanics
                summary = format_slot_scaling_summary(
                    mechanics, spell_id=spell_id
                )
                self.assertIsNotNone(summary, spell_id)
                self.assertIn("Emplacement supérieur", summary)

    def test_upcast_damage_matches_display_summary(self):
        """Slot supérieur : le cast applique le delta annoncé par mechanics_display."""
        cases: list[tuple[str, Character, str, list[int], object]] = [
            (
                "magic_missile",
                Character(
                    owner_id="1",
                    name="W",
                    race_id="human",
                    class_id="wizard",
                    level=5,
                    ability_scores=AbilityScores(
                        scores=dict.fromkeys(
                            ("str", "dex", "con", "int", "wis", "cha"), 10
                        )
                    ),
                    choices={
                        "spellcasting": {
                            "cantrips_known": ["fire_bolt"],
                            "spells_prepared": ["magic_missile"],
                            "slots_used": {"1": 4, "2": 3},
                        }
                    },
                ),
                "missiles",
                [2, 2, 2, 2, 2],
                5,
            ),
            (
                "burning_hands",
                Character(
                    owner_id="1",
                    name="W",
                    race_id="human",
                    class_id="wizard",
                    level=5,
                    ability_scores=AbilityScores(
                        scores=dict.fromkeys(
                            ("str", "dex", "con", "int", "wis", "cha"), 10
                        )
                        | {"int": 16}
                    ),
                    choices={
                        "spellcasting": {
                            "cantrips_known": ["fire_bolt"],
                            "spells_prepared": ["burning_hands"],
                            "slots_used": {1: 4, 2: 3},
                        }
                    },
                ),
                "damage_dice",
                [4, 4, 4, 4, 4],
                20,
            ),
        ]
        for spell_id, char, scaling_key, rng_values, expected_total in cases:
            with self.subTest(spell_id=spell_id):
                entry = self.engine.get_entity("spell", spell_id)
                mechanics = entry.definition.mechanics
                summary = format_slot_scaling_summary(
                    mechanics, spell_id=spell_id
                )
                self.assertIsNotNone(summary)
                increment = mechanics["slot_scaling"]["per_slot_above_base"]
                self.assertIn(scaling_key, increment)

                result = cast_spell(
                    char,
                    spell_id,
                    self.engine,
                    rng=SequenceRng(rng_values),
                    persist_slots=False,
                )
                lines = build_spell_display_lines(
                    result,
                    spell_mechanics=mechanics,
                    character_level=char.level,
                )
                display_text = "\n".join(lines)
                self.assertIn("Emplacement supérieur", display_text)
                if scaling_key == "missiles":
                    self.assertEqual(len(result.attack_rolls), expected_total)
                else:
                    self.assertEqual(result.damage_total, expected_total)
                self.assertGreater(result.slot_consumed_level or 0, result.spell_level)


if __name__ == "__main__":
    unittest.main(verbosity=2)
