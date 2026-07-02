# tests/unit/test_lore_text.py
import unittest

from interfaces.discord.formatters.lore_text import (
    clean_lore_markdown,
    combine_lore_sections,
    truncate_lore,
)


class TestLoreText(unittest.TestCase):
    def test_clean_lore_markdown_strips_headers(self):
        raw = "# Titre\n\nUn **peuple** *noble*."
        self.assertEqual(clean_lore_markdown(raw), "Titre Un peuple noble.")

    def test_truncate_lore_adds_ellipsis(self):
        text = " ".join(["mot"] * 100)
        result = truncate_lore(text, max_length=50)
        self.assertTrue(result.endswith("…"))
        self.assertLessEqual(len(result), 50)

    def test_combine_lore_sections(self):
        result = combine_lore_sections(
            [
                ("Halfelin", "Les halfelins sont courageux."),
                ("Rôdeur", "Le rôdeur traque ses proies."),
            ]
        )
        self.assertIn("Halfelin", result)
        self.assertIn("Rôdeur", result)

    def test_combine_lore_sections_empty(self):
        self.assertIsNone(combine_lore_sections([]))


if __name__ == "__main__":
    unittest.main()
