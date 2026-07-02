# jdr_engine/compendium/entry.py
"""Représentation d'une entrée Compendium chargée."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jdr_engine.compendium.schemas import DefinitionSchema


@dataclass(frozen=True)
class CompendiumEntry:
    """Une entité du Compendium (definition + chemins)."""

    ruleset_id: str
    entity_type: str          # singulier : race, class, trait
    plural_type: str          # dossier : races, classes, traits
    entry_id: str
    definition: DefinitionSchema
    entry_dir: Path

    @property
    def ref_key(self) -> str:
        return f"{self.plural_type}/{self.entry_id}"

    def get_name(self, locale: str, fallback_locale: str = "en") -> str:
        names = self.definition.name
        if locale in names:
            return names[locale]
        if fallback_locale in names:
            return names[fallback_locale]
        return next(iter(names.values()))


@dataclass(frozen=True)
class EntitySummary:
    """Résumé pour listes / menus."""

    entity_type: str
    entry_id: str
    name: dict[str, str]
    ref: str

    def display_name(self, locale: str, fallback: str = "en") -> str:
        if locale in self.name:
            return self.name[locale]
        if fallback in self.name:
            return self.name[fallback]
        return next(iter(self.name.values()))
