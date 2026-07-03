# tests/unit/test_wizard_spellcasting.py
"""Magicien — lanceur de sorts SRD 2014 niv. 1-3 (Lot B)."""
from __future__ import annotations

import unittest

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting import (
    cast_spell,
    get_max_spell_slots,
    get_remaining_slots,
    spell_attack_bonus,
    spell_save_dc,
)
from jdr_engine.rules.spellcasting.cast import build_spell_display_lines
from jdr_engine.rules.spellcasting.state import (
    consume_spell_slot,
    get_slots_used,
    reset_spell_slots,
)


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


def _wizard(
    level: int = 1,
    *,
    int_score: int = 16,
    slots_used: dict[int, int] | None = None,
    cantrips: list[str] | None = None,
    prepared: list[str] | None = None,
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
                "cantrips_known": cantrips or ["fire_bolt"],
                "spells_prepared": prepared
                or ["chromatic_orb", "burning_hands", "detect_magic", "scorching_ray"],
                "slots_used": {str(k): v for k, v in (slots_used or {}).items()},
            }
        },
    )


class TestWizardSpellStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_spell_save_dc_srd(self):
        # INT 16 (+3), niv.1 prof +2 → DD = 8 + 2 + 3 = 13
        self.assertEqual(spell_save_dc(2, 3), 13)

    def test_spell_attack_bonus_srd(self):
        # prof +2, INT +3 → +5
        self.assertEqual(spell_attack_bonus(2, 3), 5)

    def test_get_spellcasting_stats_via_cast_context(self):
        from jdr_engine.rules.spellcasting.cast import get_spellcasting_stats

        char = _wizard(1, int_score=16)
        mod, attack, dc = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod, 3)
        self.assertEqual(attack, 5)
        self.assertEqual(dc, 13)


class TestWizardSpellSlots(unittest.TestCase):
    def test_max_slots_level_1_to_3(self):
        self.assertEqual(get_max_spell_slots("wizard", 1), {1: 2})
        self.assertEqual(get_max_spell_slots("wizard", 2), {1: 3})
        self.assertEqual(get_max_spell_slots("wizard", 3), {1: 4, 2: 2})

    def test_consume_slot_level_1(self):
        char = _wizard(1)
        updated = consume_spell_slot(char, 1)
        self.assertEqual(get_slots_used(updated), {1: 1})
        self.assertEqual(get_remaining_slots("wizard", 1, get_slots_used(updated)), {1: 1})

    def test_consume_higher_slot_when_lower_empty(self):
        char = _wizard(3, slots_used={1: 4})
        updated = consume_spell_slot(char, 1)
        self.assertEqual(get_slots_used(updated), {1: 4, 2: 1})

    def test_reset_slots(self):
        char = _wizard(2, slots_used={1: 2})
        reset = reset_spell_slots(char)
        self.assertEqual(get_slots_used(reset), {})


class TestWizardSpellCast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_fire_bolt_attack_no_slot(self):
        char = _wizard(1)
        rng = SequenceRng([14, 7])  # d20=14, 1d10=7
        result = cast_spell(char, "fire_bolt", self.engine, rng=rng, persist_slots=True)
        self.assertEqual(result.spell_level, 0)
        self.assertIsNone(result.slot_consumed_level)
        self.assertEqual(result.attack_bonus, 5)
        self.assertEqual(result.attack_rolls[0].d20_result.total, 19)
        self.assertEqual(result.damage_total, 7)
        self.assertEqual(get_slots_used(result.updated_character), {})

    def test_burning_hands_save_and_slot(self):
        char = _wizard(1)
        rng = SequenceRng([4, 5, 6])  # 3d6
        result = cast_spell(char, "burning_hands", self.engine, rng=rng, persist_slots=True)
        self.assertEqual(result.save_dc, 13)
        self.assertEqual(result.save_ability, "dex")
        self.assertEqual(result.damage_total, 15)
        self.assertEqual(result.slot_consumed_level, 1)
        self.assertEqual(get_slots_used(result.updated_character), {1: 1})

    def test_detect_magic_utility(self):
        char = _wizard(1)
        result = cast_spell(char, "detect_magic", self.engine, persist_slots=True)
        self.assertEqual(result.effect_type, "utility")
        self.assertIn("magie", (result.utility_text or "").lower())
        self.assertEqual(result.slot_consumed_level, 1)

    def test_scorching_ray_three_attacks(self):
        char = _wizard(3)
        rng = SequenceRng([10, 12, 14, 3, 4, 3, 4, 5, 4, 5, 6])  # 3×(d20 + 2d6)
        result = cast_spell(char, "scorching_ray", self.engine, rng=rng, persist_slots=True)
        self.assertEqual(len(result.attack_rolls), 3)
        self.assertEqual(result.slot_consumed_level, 2)

    def test_display_lines_fire_bolt(self):
        char = _wizard(1)
        rng = SequenceRng([14, 7])
        result = cast_spell(char, "fire_bolt", self.engine, rng=rng)
        lines = build_spell_display_lines(result)
        text = "\n".join(lines)
        self.assertIn("+5", text)
        self.assertIn("**19**", text)
        self.assertIn("Emplacements : aucun consommé", text)

    def test_display_lines_burning_hands(self):
        char = _wizard(1)
        rng = SequenceRng([4, 5, 6])
        result = cast_spell(char, "burning_hands", self.engine, rng=rng, persist_slots=True)
        lines = build_spell_display_lines(result)
        text = "\n".join(lines)
        self.assertIn("DD de sauvegarde DEX : **13**", text)
        self.assertIn("Emplacements restants", text)


class TestSpellCompendium(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_five_lot_b_spells_loaded(self):
        ids = {"fire_bolt", "chromatic_orb", "burning_hands", "detect_magic", "scorching_ray"}
        for spell_id in ids:
            self.assertIsNotNone(self.engine.get_entity("spell", spell_id), spell_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
