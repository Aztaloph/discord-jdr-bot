# jdr_engine/persistence/migrations/v1_to_v2.py
"""Migration personnages v1 (bot legacy) → v2 (moteur)."""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.character_repository import (
    JsonCharacterRepository,
    get_v1_characters_path,
    get_v2_characters_path,
)

logger = logging.getLogger(__name__)

# Mapping noms français v1 → ids Compendium
RACE_NAME_TO_ID: dict[str, str] = {
    "humain": "human",
    "human": "human",
    "elfe": "elf",
    "elf": "elf",
    "nain": "dwarf",
    "dwarf": "dwarf",
    "halfelin": "halfling",
    "halfling": "halfling",
}

CLASS_NAME_TO_ID: dict[str, str] = {
    "guerrier": "fighter",
    "fighter": "fighter",
    "magicien": "wizard",
    "wizard": "wizard",
    "rodeur": "rogue",
    "rôdeur": "rogue",
    "rogue": "rogue",
    "clerc": "cleric",
    "cleric": "cleric",
}


def _map_race_id(raw: str) -> str:
    key = raw.strip().lower()
    if key in RACE_NAME_TO_ID:
        return RACE_NAME_TO_ID[key]
    raise ValueError(f"Race v1 non mappable : {raw!r}")


def _map_class_id(raw: str) -> str:
    key = raw.strip().lower()
    if key in CLASS_NAME_TO_ID:
        return CLASS_NAME_TO_ID[key]
    raise ValueError(f"Classe v1 non mappable : {raw!r}")


def convert_v1_record(raw: dict, ruleset_version: str = "1.0.0") -> Character:
    """Convertit un enregistrement v1 en Character v2."""
    return Character(
        id=raw["id"],
        owner_id=str(raw["owner_id"]),
        name=raw["nom"],
        race_id=_map_race_id(raw["race"]),
        class_id=_map_class_id(raw["classe"]),
        level=int(raw["niveau"]),
        ruleset_id="dnd5e",
        ruleset_version=ruleset_version,
        schema_version="1.0",
        ability_scores=AbilityScores.from_legacy(raw.get("caracteristiques", {})),
        hp_current=int(raw.get("pv_actuels")) if raw.get("pv_actuels") is not None else None,
        xp=0,
        image_url=raw.get("image_url"),
        inventory=[],
        choices={},
    )


def migrate_v1_to_v2(
    *,
    v1_path: Path | None = None,
    v2_repo: JsonCharacterRepository | None = None,
    ruleset_version: str = "1.0.0",
    backup: bool = True,
) -> list[Character]:
    """
    Migre data/characters/characters.json → data/characters/v2/characters.json.

    Ne modifie pas le fichier v1. Crée une sauvegarde du v2 existant si backup=True.
    """
    source = v1_path or get_v1_characters_path()
    repo = v2_repo or JsonCharacterRepository()

    if not source.exists():
        logger.info("Aucun fichier v1 à migrer : %s", source)
        return []

    if backup and repo.json_path.exists():
        repo.backup()

    with open(source, "r", encoding="utf-8") as handle:
        v1_data = json.load(handle)

    migrated: list[Character] = []
    for raw in v1_data.get("characters", {}).values():
        character = convert_v1_record(raw, ruleset_version=ruleset_version)
        repo.save(character)
        migrated.append(character)
        logger.info(
            "Migré v1→v2 : %s (%s) race=%s class=%s",
            character.name,
            character.id,
            character.race_id,
            character.class_id,
        )

    return migrated


def backup_v1(v1_path: Path | None = None) -> Path | None:
    source = v1_path or get_v1_characters_path()
    if not source.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = source.with_suffix(f".{stamp}.bak.json")
    shutil.copy2(source, dest)
    return dest
