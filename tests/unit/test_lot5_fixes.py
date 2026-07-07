# tests/unit/test_lot5_fixes.py
"""Lot 5 correctifs — métamagie, hellish_rebuke, scorching_ray, armes FR."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.class_basics import format_weapon_proficiencies
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import apply_level_up
from jdr_engine.rules.spellcasting.cast import SpellCastError, cast_spell
from jdr_engine.rules.spellcasting.state import (
    get_spellbook,
    get_spells_prepared_list,
    list_castable_spell_ids,
    list_spell_autocomplete_ids,
)
from tests.helpers.creation import sorcerer_creation_kwargs, wizard_creation_kwargs


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestLot5Fixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_hellish_rebuke_casts(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="M",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        prepared = list(get_spells_prepared_list(char))
        if "hellish_rebuke" not in prepared:
            char.choices["spellcasting"]["spells_prepared"] = prepared + ["hellish_rebuke"]
        rng = SequenceRng([5, 5])
        result = cast_spell(char, "hellish_rebuke", self.engine, rng=rng)
        self.assertEqual(result.effect_type, "saving_throw")
        self.assertEqual(result.damage_total, 10)
        self.assertIn("Réaction", result.utility_text or "")

    def test_multi_attack_spells_cast(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="M",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, subclass="evocation")
        char, _ = apply_level_up(char, self.engine)
        for spell_id in ("magic_missile", "chromatic_orb", "scorching_ray"):
            prepared = get_spells_prepared_list(char)
            if spell_id not in prepared:
                char.choices["spellcasting"]["spells_prepared"] = prepared + [spell_id]
            if spell_id == "scorching_ray":
                rng = SequenceRng([12, 12, 12, 4, 4, 4, 4, 4, 4])
            elif spell_id == "magic_missile":
                rng = SequenceRng([12, 12, 12, 3, 3, 3])
            else:
                rng = SequenceRng([12, 4, 4, 4])
            result = cast_spell(char, spell_id, self.engine, rng=rng, persist_slots=False)
            self.assertIsNotNone(result.damage_total)

    def test_scorching_ray_prepared_and_autocomplete_at_level_3(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine, subclass="evocation")
        char, _ = apply_level_up(char, self.engine)
        self.assertIn("scorching_ray", get_spellbook(char))
        self.assertIn("scorching_ray", get_spells_prepared_list(char))
        self.assertIn("scorching_ray", list_spell_autocomplete_ids(char))
        self.assertIn("scorching_ray", list_castable_spell_ids(char))

    def test_sorcerer_weapons_french(self):
        text = format_weapon_proficiencies(self.engine, "sorcerer")
        self.assertIn("Dagues", text)
        self.assertIn("Fléchettes", text)
        self.assertIn("Bâtons", text)
        self.assertIn("Frondes", text)
        self.assertNotIn("dagger", text)

    def test_sorcerer_metamagic_level_3(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Kael",
            engine=self.engine,
            **sorcerer_creation_kwargs(level=1),
        )
        char, _ = apply_level_up(char, self.engine)
        char, result = apply_level_up(
            char, self.engine, metamagic_options=["quickened", "extended"]
        )
        self.assertEqual(result.new_level, 3)
        self.assertEqual(char.choices.get("metamagic_options"), ["quickened", "extended"])
        sheet = build_character_sheet(char, self.engine)
        joined = "\n".join(sheet.class_features_lines)
        self.assertIn("accéléré", joined.lower())

    def test_wizard_grimoire_unchanged_after_fixes(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Merlin",
            engine=self.engine,
            **wizard_creation_kwargs(level=1),
        )
        self.assertEqual(len(get_spellbook(char)), 6)
        self.assertGreater(len(get_spells_prepared_list(char)), 0)
        unprepared = [
            s
            for s in get_spellbook(char)
            if s not in get_spells_prepared_list(char)
        ]
        if unprepared:
            with self.assertRaises(SpellCastError):
                cast_spell(char, unprepared[0], self.engine)


if __name__ == "__main__":
    unittest.main(verbosity=2)
