# tests/compendium/test_dnd5e_integrity.py
"""Validation intégrité complète du Compendium dnd5e."""
import unittest

from jdr_engine.compendium.loader import load_ruleset
from jdr_engine.compendium.registry import CompendiumRegistry
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.compendium.validator import validate_registry
from jdr_engine.rules import RuleEngine


class TestDnd5eIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")

    def test_validation_no_errors(self):
        manifest, config, entries = load_ruleset("dnd5e")
        registry = CompendiumRegistry(manifest, config, entries)
        report = validate_registry(registry, schema_strict=True)
        errors = [i for i in report.issues if i.level == "error"]
        self.assertEqual(
            errors,
            [],
            msg="\n".join(f"{e.code}: {e.message}" for e in errors),
        )

    def test_validation_schema_strict_no_mechanics_errors(self):
        manifest, config, entries = load_ruleset("dnd5e")
        registry = CompendiumRegistry(manifest, config, entries)
        report = validate_registry(registry, schema_strict=True)
        schema_errors = [
            i for i in report.issues
            if i.level == "error" and i.code == "mechanics_schema"
        ]
        self.assertEqual(schema_errors, [])

    def test_rule_engine_load_strict(self):
        engine = RuleEngine.load("dnd5e", strict=True)
        self.assertEqual(engine.ruleset_id, "dnd5e")
        self.assertEqual(engine.ruleset_version, "1.0.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
