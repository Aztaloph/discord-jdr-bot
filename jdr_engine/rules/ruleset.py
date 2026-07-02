# jdr_engine/rules/ruleset.py
"""Contexte d'un ruleset chargé."""
from __future__ import annotations

from jdr_engine.compendium.loader import load_ruleset
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.compendium.registry import CompendiumRegistry
from jdr_engine.compendium.validator import ValidationReport, validate_registry


class RulesetContext:
    """Ruleset chargé : registry + validation."""

    def __init__(self, registry: CompendiumRegistry):
        self.registry = registry

    @classmethod
    def load(
        cls,
        ruleset_id: str,
        *,
        validate: bool = True,
        strict: bool = True,
    ) -> RulesetContext:
        if not get_ruleset_path(ruleset_id).is_dir():
            raise FileNotFoundError(f"Ruleset introuvable : {ruleset_id}")

        manifest, config, entries = load_ruleset(ruleset_id)
        registry = CompendiumRegistry(manifest, config, entries)

        if validate:
            report = validate_registry(registry, schema_strict=strict)
            if not report.ok and strict:
                messages = "\n".join(
                    f"  [{i.level}] {i.code}: {i.message} ({i.ref})"
                    for i in report.issues
                    if i.level == "error"
                )
                raise ValueError(
                    f"Compendium {ruleset_id} invalide :\n{messages}"
                )
            ctx = cls(registry)
            ctx._last_validation = report  # type: ignore[attr-defined]
            return ctx

        return cls(registry)

    def validate(self) -> ValidationReport:
        return validate_registry(self.registry)
