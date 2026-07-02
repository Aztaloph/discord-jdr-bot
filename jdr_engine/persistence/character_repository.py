# jdr_engine/persistence/character_repository.py
"""Repository JSON pour les personnages v2."""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from jdr_engine.compendium.paths import get_project_root
from jdr_engine.domain.character.character import Character

logger = logging.getLogger(__name__)

PERSISTENCE_SCHEMA_VERSION = "1.0"


def get_v2_characters_path() -> Path:
    return get_project_root() / "data" / "characters" / "v2" / "characters.json"


def get_v1_characters_path() -> Path:
    return get_project_root() / "data" / "characters" / "characters.json"


class JsonCharacterRepository:
    """Persistance des personnages v2 dans un fichier JSON."""

    def __init__(self, json_path: Path | None = None):
        self.json_path = json_path or get_v2_characters_path()
        self.json_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_raw(self) -> dict:
        if not self.json_path.exists():
            return {
                "schema_version": PERSISTENCE_SCHEMA_VERSION,
                "characters": {},
            }
        with open(self.json_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save_raw(self, data: dict) -> None:
        with open(self.json_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def save(self, character: Character) -> None:
        data = self._load_raw()
        chars = data.setdefault("characters", {})
        chars[character.id] = character.to_dict()
        data["schema_version"] = PERSISTENCE_SCHEMA_VERSION
        self._save_raw(data)
        logger.info("Personnage v2 sauvegardé : %s (%s)", character.name, character.id)

    def get_by_id(self, character_id: str) -> Character | None:
        data = self._load_raw()
        raw = data.get("characters", {}).get(character_id)
        if raw is None:
            return None
        return Character.from_dict(raw)

    def get_by_name(self, name: str, owner_id: str) -> Character | None:
        owner = str(owner_id)
        name_lower = name.strip().lower()
        for char in self.list_by_owner(owner):
            if char.name.lower() == name_lower:
                return char
        return None

    def list_by_owner(self, owner_id: str) -> list[Character]:
        owner = str(owner_id)
        data = self._load_raw()
        result: list[Character] = []
        for raw in data.get("characters", {}).values():
            if str(raw.get("owner_id")) == owner:
                result.append(Character.from_dict(raw))
        result.sort(key=lambda c: c.name.lower())
        return result

    def delete(self, character_id: str) -> bool:
        data = self._load_raw()
        chars = data.get("characters", {})
        if character_id not in chars:
            return False
        del chars[character_id]
        self._save_raw(data)
        return True

    def name_exists(
        self,
        name: str,
        owner_id: str,
        exclude_id: str | None = None,
    ) -> bool:
        existing = self.get_by_name(name, owner_id)
        if existing is None:
            return False
        if exclude_id and existing.id == exclude_id:
            return False
        return True

    def backup(self, suffix: str | None = None) -> Path | None:
        if not self.json_path.exists():
            return None
        stamp = suffix or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = self.json_path.with_suffix(f".{stamp}.bak.json")
        shutil.copy2(self.json_path, backup_path)
        return backup_path
