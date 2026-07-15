# tests/unit/test_creer_perso_display_copy.py
"""Textes d'affichage /creer-perso — à jour avec tous les lanceurs SRD."""
from __future__ import annotations

import unittest

from interfaces.discord.views.creer_perso_wizard import CREATION_SRD_CLASSES_HINT


class TestCreerPersoDisplayCopy(unittest.TestCase):
    def test_creation_hint_mentions_all_classes_and_sort(self):
        self.assertIn("12 classes SRD", CREATION_SRD_CLASSES_HINT)
        self.assertIn("/sort", CREATION_SRD_CLASSES_HINT)
        self.assertNotIn("lots ultérieurs", CREATION_SRD_CLASSES_HINT)
        self.assertNotIn("Magicien et Clerc", CREATION_SRD_CLASSES_HINT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
