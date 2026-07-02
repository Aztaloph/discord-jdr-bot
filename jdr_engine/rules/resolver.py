# jdr_engine/rules/resolver.py
"""Résolution des références entre entrées Compendium."""
from __future__ import annotations

from typing import Any

from jdr_engine.compendium.entry import CompendiumEntry
from jdr_engine.compendium.registry import CompendiumRegistry
from jdr_engine.compendium.schemas import EntityRef


class ReferenceResolutionError(Exception):
    """Référence Compendium introuvable."""


def resolve_ref(registry: CompendiumRegistry, ref: str) -> CompendiumEntry:
    entry = registry.get_by_ref(ref)
    if entry is None:
        raise ReferenceResolutionError(f"Référence introuvable : {ref!r}")
    return entry


def resolve_trait_refs(
    registry: CompendiumRegistry,
    mechanics: dict[str, Any],
) -> list[CompendiumEntry]:
    """Déplie les traits référencés dans mechanics.traits."""
    resolved: list[CompendiumEntry] = []
    for item in mechanics.get("traits", []):
        ref_str: str | None = None
        if isinstance(item, dict) and "ref" in item:
            ref_str = item["ref"]
        elif isinstance(item, str) and "/" in item:
            ref_str = item
        if ref_str:
            resolved.append(resolve_ref(registry, ref_str))
    return resolved


def parse_entity_ref(raw: dict | str) -> EntityRef | None:
    if isinstance(raw, dict) and "ref" in raw:
        return EntityRef.model_validate(raw)
    if isinstance(raw, str) and "/" in raw:
        return EntityRef(ref=raw)
    return None
