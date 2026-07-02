# jdr_engine/compendium/registry.py
"""Index des entrées Compendium en mémoire."""
from __future__ import annotations

from jdr_engine.compendium.entry import CompendiumEntry, EntitySummary
from jdr_engine.compendium.schemas import (
    RulesetConfig,
    RulesetManifest,
    normalize_entity_type,
    plural_entity_type,
)


class CompendiumRegistry:
    """Registre read-only des entrées d'un ruleset."""

    def __init__(
        self,
        manifest: RulesetManifest,
        config: RulesetConfig,
        entries: list[CompendiumEntry],
    ):
        self.manifest = manifest
        self.config = config
        self._by_ref: dict[str, CompendiumEntry] = {}
        self._by_type: dict[str, list[CompendiumEntry]] = {}

        for entry in entries:
            ref = entry.ref_key
            if ref in self._by_ref:
                raise ValueError(f"ID dupliqué dans le Compendium : {ref}")
            self._by_ref[ref] = entry
            self._by_type.setdefault(entry.entity_type, []).append(entry)

        for entity_type in self._by_type:
            self._by_type[entity_type].sort(key=lambda e: e.entry_id)

    @property
    def ruleset_id(self) -> str:
        return self.manifest.id

    @property
    def version(self) -> str:
        return self.manifest.version

    def get_by_ref(self, ref: str) -> CompendiumEntry | None:
        return self._by_ref.get(ref)

    def get(self, entity_type: str, entry_id: str) -> CompendiumEntry | None:
        singular = normalize_entity_type(entity_type)
        plural = plural_entity_type(singular)
        return self._by_ref.get(f"{plural}/{entry_id}")

    def list_entries(self, entity_type: str) -> list[CompendiumEntry]:
        singular = normalize_entity_type(entity_type)
        return list(self._by_type.get(singular, []))

    def list_summaries(self, entity_type: str) -> list[EntitySummary]:
        return [
            EntitySummary(
                entity_type=e.entity_type,
                entry_id=e.entry_id,
                name=dict(e.definition.name),
                ref=e.ref_key,
            )
            for e in self.list_entries(entity_type)
        ]

    def all_refs(self) -> set[str]:
        return set(self._by_ref.keys())

    def __len__(self) -> int:
        return len(self._by_ref)
