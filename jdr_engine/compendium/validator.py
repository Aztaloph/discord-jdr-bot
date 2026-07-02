# jdr_engine/compendium/validator.py
"""Validation intégrité Compendium (L1-L3)."""
from __future__ import annotations

from dataclasses import dataclass, field

from jdr_engine.compendium.registry import CompendiumRegistry
from jdr_engine.compendium.mechanics_schema import validate_entry_mechanics


@dataclass
class ValidationIssue:
    level: str          # error | warning
    code: str
    message: str
    ref: str | None = None


@dataclass
class ValidationReport:
    ruleset_id: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "warning")

    def add_error(self, code: str, message: str, ref: str | None = None) -> None:
        self.issues.append(ValidationIssue("error", code, message, ref))

    def add_warning(self, code: str, message: str, ref: str | None = None) -> None:
        self.issues.append(ValidationIssue("warning", code, message, ref))


def _collect_refs_from_mechanics(mechanics: dict) -> list[str]:
    refs: list[str] = []
    traits = mechanics.get("traits", [])
    for item in traits:
        if isinstance(item, dict) and "ref" in item:
            refs.append(item["ref"])
        elif isinstance(item, str) and "/" in item:
            refs.append(item)
    return refs


def validate_registry(
    registry: CompendiumRegistry,
    *,
    check_lore: bool = True,
    check_mechanics_schema: bool = True,
    schema_strict: bool = False,
) -> ValidationReport:
    """
    L1 : déjà fait au load (Pydantic)
    L2 : références cassées
    L3 : cohérence id / type (déjà au load)
    L4 : JSON Schema mechanics (race / class)
    L5 (warn) : lore manquant pour locales déclarées
    """
    report = ValidationReport(ruleset_id=registry.ruleset_id)
    all_refs = registry.all_refs()

    # L2 — références
    for entry in registry.list_entries("race") + registry.list_entries("class"):
        for ref_str in _collect_refs_from_mechanics(entry.definition.mechanics):
            if ref_str not in all_refs:
                report.add_error(
                    "broken_ref",
                    f"Référence introuvable : {ref_str!r}",
                    ref=entry.ref_key,
                )

    # L4 — JSON Schema mechanics
    if check_mechanics_schema:
        for entity_type in ("race", "class"):
            for entry in registry.list_entries(entity_type):
                errors = validate_entry_mechanics(
                    entity_type, entry.definition.mechanics
                )
                for message in errors:
                    issue = (
                        report.add_error
                        if schema_strict
                        else report.add_warning
                    )
                    issue(
                        "mechanics_schema",
                        message,
                        ref=entry.ref_key,
                    )

    # L5 — lore (warnings)
    if check_lore:
        for locale in registry.manifest.locales:
            for entry in registry.list_entries("race"):
                lore_path = entry.entry_dir / f"lore.{locale}.md"
                if not lore_path.exists():
                    report.add_warning(
                        "missing_lore",
                        f"lore.{locale}.md manquant",
                        ref=entry.ref_key,
                    )

    # config abilities referenced in races
    ability_ids = {a.id for a in registry.config.abilities}
    for entry in registry.list_entries("race"):
        for bonus in entry.definition.mechanics.get("ability_score_increase", []):
            ability = bonus.get("ability") if isinstance(bonus, dict) else None
            if ability and ability not in ability_ids:
                report.add_error(
                    "unknown_ability",
                    f"Caractéristique inconnue : {ability!r}",
                    ref=entry.ref_key,
                )

    return report
