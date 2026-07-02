# tests/unit/test_compendium_loader.py
import unittest
from pathlib import Path

from jdr_engine.compendium.loader import load_ruleset
from jdr_engine.compendium.registry import CompendiumRegistry
from jdr_engine.compendium.paths import get_ruleset_path


class TestCompendiumLoader(unittest.TestCase):
    """Charge le Compendium dnd5e minimal."""

    @classmethod
    def setUpClass(cls):
        cls.ruleset_path = get_ruleset_path("dnd5e")
        if not cls.ruleset_path.is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")
        cls.manifest, cls.config, cls.entries = load_ruleset("dnd5e")
        cls.registry = CompendiumRegistry(cls.manifest, cls.config, cls.entries)

    def test_manifest(self):
        self.assertEqual(self.manifest.id, "dnd5e")
        self.assertIn("fr", self.manifest.locales)

    def test_entry_count(self):
        # 4 races + 7 classes + 29 traits = 40
        self.assertEqual(len(self.registry), 40)

    def test_races_loaded(self):
        races = self.registry.list_entries("race")
        ids = {r.entry_id for r in races}
        self.assertEqual(ids, {"human", "elf", "dwarf", "halfling"})

    def test_classes_loaded(self):
        classes = self.registry.list_entries("class")
        ids = {c.entry_id for c in classes}
        self.assertEqual(ids, {"fighter", "wizard", "rogue", "cleric", "ranger", "barbarian", "monk"})

    def test_traits_loaded(self):
        traits = self.registry.list_entries("trait")
        self.assertEqual(len(traits), 29)

    def test_elf_definition_path(self):
        elf = self.registry.get("race", "elf")
        self.assertIsNotNone(elf)
        self.assertTrue((elf.entry_dir / "definition.yaml").exists())
        self.assertTrue((elf.entry_dir / "lore.fr.md").exists())

    def test_no_duplicate_refs(self):
        refs = list(self.registry.all_refs())
        self.assertEqual(len(refs), len(set(refs)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
