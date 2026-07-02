# jdr_engine/compendium/presenter.py
"""Accès au contenu narratif (lore, assets) — non utilisé par le Rule Engine."""
from __future__ import annotations

from pathlib import Path

from jdr_engine.compendium.registry import CompendiumRegistry


class CompendiumPresenter:
    """Lit lore.md et chemins assets pour les interfaces."""

    def __init__(self, registry: CompendiumRegistry):
        self._registry = registry

    def get_lore(
        self,
        entity_type: str,
        entry_id: str,
        locale: str,
        fallback_locale: str | None = None,
    ) -> str | None:
        entry = self._registry.get(entity_type, entry_id)
        if entry is None:
            return None

        fallback = fallback_locale or self._registry.manifest.default_locale
        for loc in (locale, fallback, "en"):
            lore_path = entry.entry_dir / f"lore.{loc}.md"
            if lore_path.exists():
                return lore_path.read_text(encoding="utf-8").strip()
        return None

    def get_asset_path(
        self,
        entity_type: str,
        entry_id: str,
        asset_name: str,
    ) -> Path | None:
        entry = self._registry.get(entity_type, entry_id)
        if entry is None:
            return None
        asset_path = entry.entry_dir / "assets" / asset_name
        return asset_path if asset_path.exists() else None

    def list_available_lore_locales(
        self,
        entity_type: str,
        entry_id: str,
    ) -> list[str]:
        entry = self._registry.get(entity_type, entry_id)
        if entry is None:
            return []
        locales = []
        for path in entry.entry_dir.glob("lore.*.md"):
            part = path.stem  # lore.fr
            if part.startswith("lore."):
                locales.append(part.split(".", 1)[1])
        return sorted(locales)
