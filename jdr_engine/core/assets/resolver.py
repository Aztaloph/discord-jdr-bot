# jdr_engine/core/assets/resolver.py
"""Résolution des chemins assets Compendium pour les interfaces."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jdr_engine.compendium.presenter import CompendiumPresenter


@dataclass(frozen=True)
class AssetReference:
    """Référence légère — le moteur ne charge jamais le fichier binaire."""

    entity_type: str
    entry_id: str
    asset_name: str


class AssetResolver:
    """Résout les assets locaux du Compendium (portraits, icônes)."""

    PORTRAIT_NAME = "portrait.png"
    ICON_NAME = "icon.png"

    def __init__(self, presenter: CompendiumPresenter):
        self._presenter = presenter

    def resolve_path(
        self,
        entity_type: str,
        entry_id: str,
        asset_name: str,
    ) -> Path | None:
        return self._presenter.get_asset_path(entity_type, entry_id, asset_name)

    def resolve_portrait(self, entity_type: str, entry_id: str) -> Path | None:
        for name in (self.PORTRAIT_NAME, "portrait.jpg", "portrait.webp"):
            path = self.resolve_path(entity_type, entry_id, name)
            if path is not None:
                return path
        return None

    def reference(self, entity_type: str, entry_id: str, asset_name: str) -> AssetReference:
        return AssetReference(
            entity_type=entity_type,
            entry_id=entry_id,
            asset_name=asset_name,
        )
