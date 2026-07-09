# tests/unit/test_p1_fix_hellish_rebuke.py
"""P1-fix — hellish_rebuke occultiste Fiélon (liste élargie)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.rules import RuleEngine
from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.spellcasting.cast import cast_spell
from jdr_engine.rules.spellcasting.state import list_spell_autocomplete_ids
from tests.helpers.creation import warlock_creation_kwargs


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


class TestHellishRebukeWarlockFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_fiend_warlock_hellish_rebuke_casts(self):
        char = finalize_new_character(
            owner_id="1",
            guild_id="1",
            name="Morrigan",
            engine=self.engine,
            **warlock_creation_kwargs(level=1),
        )
        self.assertIn("hellish_rebuke", list_spell_autocomplete_ids(char))
        rng = SequenceRng([5, 5])
        result = cast_spell(char, "hellish_rebuke", self.engine, rng=rng)
        self.assertEqual(result.effect_type, "saving_throw")
        self.assertEqual(result.save_ability, "dex")
        self.assertEqual(result.damage_total, 10)
        self.assertIn("Réaction", result.utility_text or "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
