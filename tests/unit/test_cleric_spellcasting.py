# tests/unit/test_cleric_spellcasting.py
"""Clerc — lanceur de sorts SRD 2014 niv. 1-3."""
from __future__ import annotations

import unittest

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting import (
    cast_spell,
    get_max_spell_slots,
    spell_attack_bonus,
    spell_save_dc,
)
from jdr_engine.rules.spellcasting.cast import build_spell_display_lines, get_spellcasting_stats


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


def _cleric(
    level: int = 3,
    *,
    wis_score: int = 16,
    hp_current: int = 10,
    prepared: list[str] | None = None,
) -> Character:
    scores = dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
    scores["wis"] = wis_score
    return Character(
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
                "spells_prepared": prepared
                or ["cure_wounds", "inflict_wounds", "bless", "spiritual_weapon"],
                "slots_used": {},
            }
        },
    )


class TestClericSpellStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_wis_save_dc_and_attack(self):
        char = _cleric(1, wis_score=16)
        mod, attack, dc = get_spellcasting_stats(char, self.engine)
        self.assertEqual(mod, 3)
        self.assertEqual(spell_attack_bonus(2, 3), attack)
        self.assertEqual(spell_save_dc(2, 3), dc)
        self.assertEqual(dc, 13)

    def test_cleric_slots_level_3(self):
        self.assertEqual(get_max_spell_slots("cleric", 3), {1: 4, 2: 2})


class TestClericSpellCast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_sacred_flame_save_no_half(self):
        char = _cleric(1)
        rng = SequenceRng([6])
        result = cast_spell(char, "sacred_flame", self.engine, rng=rng)
        self.assertEqual(result.save_dc, 13)
        self.assertFalse(result.half_on_save)
        text = "\n".join(build_spell_display_lines(result))
        self.assertIn("Aucun dégât en cas de réussite", text)

    def test_cure_wounds_healing_updates_hp(self):
        char = _cleric(3, hp_current=10)
        char.hp_max = 24
        rng = SequenceRng([5])  # 1d8=5 +3 mod = 8
        result = cast_spell(char, "cure_wounds", self.engine, rng=rng, persist_slots=True)
        self.assertEqual(result.healing_total, 8)
        self.assertEqual(result.healing_applied, 8)
        self.assertEqual(result.hp_before, 10)
        self.assertEqual(result.hp_after, 18)
        self.assertEqual(result.hp_max, 24)
        self.assertFalse(result.healing_capped)
        self.assertEqual(result.updated_character.hp_current, 18)

    def test_cure_wounds_capped_at_hp_max(self):
        char = _cleric(3, hp_current=18)
        char.hp_max = 24
        rng = SequenceRng([5])  # jet 8, gain effectif +6 seulement
        result = cast_spell(char, "cure_wounds", self.engine, rng=rng, persist_slots=True)
        self.assertEqual(result.healing_total, 8)
        self.assertEqual(result.healing_applied, 6)
        self.assertEqual(result.hp_after, 24)
        self.assertTrue(result.healing_capped)
        text = "\n".join(build_spell_display_lines(result))
        self.assertIn("plafonné", text)
        self.assertIn("maximum atteint", text)

    def test_cure_wounds_no_gain_when_already_full(self):
        char = _cleric(3, hp_current=24)
        char.hp_max = 24
        rng = SequenceRng([8])
        result = cast_spell(char, "cure_wounds", self.engine, rng=rng, persist_slots=True)
        self.assertEqual(result.healing_applied, 0)
        self.assertEqual(result.hp_after, 24)
        text = "\n".join(build_spell_display_lines(result))
        self.assertIn("déjà au maximum", text)

    def test_bless_concentration_buff(self):
        char = _cleric(1)
        result = cast_spell(char, "bless", self.engine, persist_slots=True)
        self.assertEqual(result.effect_type, "buff")
        self.assertTrue(result.concentration)
        conc = result.updated_character.choices["spellcasting"]["concentration"]
        self.assertEqual(conc["spell_id"], "bless")
        text = "\n".join(build_spell_display_lines(result))
        self.assertIn("Concentration", text)
        self.assertIn("1d4", text)

    def test_inflict_wounds_melee_attack(self):
        char = _cleric(1)
        rng = SequenceRng([15, 8, 9, 10])  # d20 + 3d10
        result = cast_spell(char, "inflict_wounds", self.engine, rng=rng)
        self.assertEqual(result.attack_bonus, 5)
        self.assertEqual(result.damage_total, 27)

    def test_spiritual_weapon_with_mod(self):
        char = _cleric(3)
        rng = SequenceRng([12, 6])  # d20 + 1d8
        result = cast_spell(char, "spiritual_weapon", self.engine, rng=rng, persist_slots=True)
        self.assertEqual(result.damage_total, 9)  # 6 + 3 mod
        self.assertEqual(result.slot_consumed_level, 2)


class TestClericSpellsCompendium(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_five_cleric_spells_loaded(self):
        ids = {
            "sacred_flame",
            "cure_wounds",
            "inflict_wounds",
            "bless",
            "spiritual_weapon",
        }
        for spell_id in ids:
            self.assertIsNotNone(self.engine.get_entity("spell", spell_id), spell_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
