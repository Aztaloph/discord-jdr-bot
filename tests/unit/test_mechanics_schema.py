# tests/unit/test_mechanics_schema.py
import unittest

from jdr_engine.compendium.mechanics_schema import (
    validate_class_mechanics,
    validate_race_mechanics,
)
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.compendium.loader import load_ruleset
from jdr_engine.compendium.registry import CompendiumRegistry
from jdr_engine.compendium.validator import validate_registry


class TestMechanicsSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not get_ruleset_path("dnd5e").is_dir():
            raise unittest.SkipTest("compendium/dnd5e absent")

    def test_halfling_and_ranger_mechanics_valid(self):
        manifest, config, entries = load_ruleset("dnd5e")
        registry = CompendiumRegistry(manifest, config, entries)
        halfling = registry.get("race", "halfling")
        ranger = registry.get("class", "ranger")
        self.assertEqual(validate_race_mechanics(halfling.definition.mechanics), [])
        self.assertEqual(validate_class_mechanics(ranger.definition.mechanics), [])

    def test_invalid_race_mechanics_detected(self):
        errors = validate_race_mechanics({"size": "medium"})
        self.assertTrue(errors)

    def test_registry_schema_strict_fails_on_invalid(self):
        manifest, config, entries = load_ruleset("dnd5e")
        registry = CompendiumRegistry(manifest, config, entries)
        report = validate_registry(registry, schema_strict=True)
        self.assertTrue(report.ok, msg=str(report.issues))


if __name__ == "__main__":
    unittest.main()
