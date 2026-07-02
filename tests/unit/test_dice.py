# tests/unit/test_dice.py
# Tests unitaires pour jdr_engine.dice
# Lance avec : python -m unittest tests.unit.test_dice -v
import unittest

from jdr_engine.dice import (
    DiceError,
    MAX_DICE,
    MAX_FACES,
    RollResult,
    parse,
    roll,
)


class TestParse(unittest.TestCase):
    """Tests de la fonction parse()."""

    def test_simple_d20(self):
        count, faces, mod, sign = parse("d20")
        self.assertEqual(count, 1)
        self.assertEqual(faces, 20)
        self.assertEqual(mod, 0)
        self.assertEqual(sign, "+")

    def test_3d6(self):
        count, faces, mod, sign = parse("3d6")
        self.assertEqual(count, 3)
        self.assertEqual(faces, 6)
        self.assertEqual(mod, 0)

    def test_1d20_plus_5(self):
        count, faces, mod, sign = parse("1d20+5")
        self.assertEqual(count, 1)
        self.assertEqual(faces, 20)
        self.assertEqual(mod, 5)
        self.assertEqual(sign, "+")

    def test_2d8_minus_1(self):
        count, faces, mod, sign = parse("2d8-1")
        self.assertEqual(count, 2)
        self.assertEqual(faces, 8)
        self.assertEqual(mod, -1)
        self.assertEqual(sign, "-")

    def test_no_prefix_count(self):
        count, faces, mod, sign = parse("4d6")
        self.assertEqual(count, 4)
        self.assertEqual(faces, 6)

    def test_d6_notation(self):
        count, faces, mod, sign = parse("d6")
        self.assertEqual(count, 1)
        self.assertEqual(faces, 6)

    def test_d6_plus_3(self):
        count, faces, mod, sign = parse("d6+3")
        self.assertEqual(count, 1)
        self.assertEqual(faces, 6)
        self.assertEqual(mod, 3)
        self.assertEqual(sign, "+")

    def test_whitespace_trimmed(self):
        count, faces, mod, sign = parse("  2d10+3  ")
        self.assertEqual(count, 2)
        self.assertEqual(faces, 10)
        self.assertEqual(mod, 3)
        self.assertEqual(sign, "+")

    def test_case_insensitive(self):
        count, faces, mod, sign = parse("D20+5")
        self.assertEqual(count, 1)
        self.assertEqual(faces, 20)

    def test_empty_raises(self):
        with self.assertRaises(DiceError):
            parse("")

    def test_empty_whitespace_raises(self):
        with self.assertRaises(DiceError):
            parse("   ")

    def test_invalid_format_raises(self):
        with self.assertRaises(DiceError):
            parse("abc")
        with self.assertRaises(DiceError):
            parse("3x6")
        with self.assertRaises(DiceError):
            parse("3d")

    def test_too_many_dice_raises(self):
        with self.assertRaises(DiceError):
            parse(f"{MAX_DICE + 1}d6")

    def test_too_many_faces_raises(self):
        with self.assertRaises(DiceError):
            parse(f"d{MAX_FACES + 1}")

    def test_zero_faces_raises(self):
        with self.assertRaises(DiceError):
            parse("d0")

    def test_zero_dice_raises(self):
        with self.assertRaises(DiceError):
            parse("0d6")

    def test_negative_faces_raises(self):
        with self.assertRaises(DiceError):
            parse("d-4")


class TestRoll(unittest.TestCase):
    """Tests de la fonction roll()."""

    def test_roll_returns_rollresult(self):
        result = roll("d6")
        self.assertIsInstance(result, RollResult)
        self.assertEqual(result.dice_notation, "d6")
        self.assertEqual(len(result.rolls), 1)
        self.assertTrue(1 <= result.rolls[0] <= 6)

    def test_roll_3d6_returns_3_rolls(self):
        result = roll("3d6")
        self.assertEqual(len(result.rolls), 3)
        for r in result.rolls:
            self.assertTrue(1 <= r <= 6)

    def test_roll_with_modifier(self):
        result = roll("2d8+3")
        self.assertEqual(result.modifier, 3)
        self.assertEqual(result.modifier_label, "+3")
        self.assertEqual(result.total, sum(result.rolls) + 3)

    def test_roll_with_negative_modifier(self):
        result = roll("4d6-2")
        self.assertEqual(result.modifier, -2)
        self.assertEqual(result.modifier_label, "-2")
        self.assertEqual(result.total, sum(result.rolls) - 2)

    def test_roll_total_is_sum_plus_modifier(self):
        result = roll("1d20+5")
        self.assertEqual(result.total, result.rolls[0] + 5)

    def test_roll_all_kept_normal_mode(self):
        result = roll("3d6", mode="normal")
        self.assertTrue(all(result.is_kept))
        self.assertEqual(result.total, sum(result.rolls) + result.modifier)

    def test_advantage_is_2d20(self):
        result = roll("d20", mode="avantage")
        self.assertEqual(len(result.rolls), 2)
        self.assertTrue(1 <= result.rolls[0] <= 20)
        self.assertTrue(1 <= result.rolls[1] <= 20)

    def test_disadvantage_is_2d20(self):
        result = roll("d20", mode="desavantage")
        self.assertEqual(len(result.rolls), 2)

    def test_advantage_keeps_best(self):
        r = roll("d20", mode="avantage")
        best = max(r.rolls)
        self.assertEqual(r.total, best + r.modifier)

    def test_disadvantage_keeps_worst(self):
        r = roll("d20", mode="desavantage")
        worst = min(r.rolls)
        self.assertEqual(r.total, worst + r.modifier)

    def test_advantage_none_d20_raises(self):
        with self.assertRaises(DiceError):
            roll("d6", mode="avantage")

    def test_disadvantage_none_d20_raises(self):
        with self.assertRaises(DiceError):
            roll("3d8", mode="desavantage")

    def test_invalid_mode_raises(self):
        with self.assertRaises(DiceError):
            roll("d20", mode="toto")

    def test_is_kept_count_matches_rolls(self):
        result = roll("3d6", mode="normal")
        self.assertEqual(len(result.is_kept), len(result.rolls))

    def test_advantage_is_kept_count(self):
        result = roll("d20", mode="avantage")
        self.assertEqual(len(result.is_kept), 2)
        self.assertEqual(sum(result.is_kept), 1)


class TestSecurityLimits(unittest.TestCase):
    """Tests des limites de sécurité."""

    def test_max_dice_boundary(self):
        result = roll(f"{MAX_DICE}d6")
        self.assertEqual(len(result.rolls), MAX_DICE)

    def test_max_faces_boundary(self):
        result = roll(f"d{MAX_FACES}")
        self.assertIsInstance(result.rolls[0], int)
        self.assertTrue(1 <= result.rolls[0] <= MAX_FACES)

    def test_max_dice_plus_one_raises(self):
        with self.assertRaises(DiceError):
            parse(f"{MAX_DICE + 1}d6")

    def test_max_faces_plus_one_raises(self):
        with self.assertRaises(DiceError):
            parse(f"d{MAX_FACES + 1}")


class TestLegacyImport(unittest.TestCase):
    """Vérifie que l'import legacy bot.utils.dice_parser fonctionne encore."""

    def test_legacy_reexport(self):
        from bot.utils.dice_parser import parse as legacy_parse, roll as legacy_roll

        self.assertEqual(legacy_parse("d20")[:2], (1, 20))
        self.assertIsInstance(legacy_roll("d6"), RollResult)


if __name__ == "__main__":
    unittest.main(verbosity=2)
