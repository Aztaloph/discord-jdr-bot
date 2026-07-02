# tests/unit/test_asset_resolver.py
import unittest
from pathlib import Path

from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.core.assets import AssetResolver
from jdr_engine.rules import RuleEngine


class TestAssetResolver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")
        cls.engine = RuleEngine.load("dnd5e", strict=False)
        cls.resolver = AssetResolver(cls.engine.presenter)

    def test_missing_portrait_returns_none(self):
        self.assertIsNone(self.resolver.resolve_portrait("race", "elf"))

    def test_resolve_path_with_existing_file(self):
        elf_dir = get_ruleset_path("dnd5e") / "entries" / "races" / "elf" / "assets"
        elf_dir.mkdir(parents=True, exist_ok=True)
        portrait = elf_dir / "portrait.png"
        try:
            portrait.write_bytes(b"\x89PNG\r\n\x1a\n")
            path = self.resolver.resolve_portrait("race", "elf")
            self.assertIsInstance(path, Path)
            self.assertTrue(path.exists())
        finally:
            if portrait.exists():
                portrait.unlink()
            if elf_dir.exists() and not any(elf_dir.iterdir()):
                elf_dir.rmdir()

    def test_reference_dataclass(self):
        ref = self.resolver.reference("race", "elf", "portrait.png")
        self.assertEqual(ref.entity_type, "race")
        self.assertEqual(ref.entry_id, "elf")


if __name__ == "__main__":
    unittest.main()
