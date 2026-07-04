# jdr_engine/domain/character/character.py
"""Entité Character — état persisté du joueur (IDs, pas texte libre)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.choices_schema import normalize_character_choices


@dataclass
class Character:
    """
    État d'un personnage — ne contient pas les règles complètes.

    Les statistiques dérivées sont calculées par le Rule Engine → CharacterSheet.
    """

    owner_id: str
    name: str
    race_id: str
    class_id: str
    level: int
    ruleset_id: str = "dnd5e"
    ruleset_version: str = "1.0.0"
    schema_version: str = "1.0"
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    guild_id: str = "0"
    ability_scores: AbilityScores = field(default_factory=AbilityScores)
    hp_current: int | None = None
    hp_max: int | None = None
    xp: int = 0
    image_url: str | None = None
    inventory: list[dict[str, Any]] = field(default_factory=list)
    choices: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "guild_id": self.guild_id,
            "name": self.name,
            "race_id": self.race_id,
            "class_id": self.class_id,
            "level": self.level,
            "ruleset_id": self.ruleset_id,
            "ruleset_version": self.ruleset_version,
            "schema_version": self.schema_version,
            "ability_scores": self.ability_scores.to_dict(),
            "hp_current": self.hp_current,
            "hp_max": self.hp_max,
            "xp": self.xp,
            "image_url": self.image_url,
            "inventory": list(self.inventory),
            "choices": normalize_character_choices(dict(self.choices)),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Character:
        ability_raw = data.get("ability_scores", {})
        return cls(
            id=data["id"],
            owner_id=str(data["owner_id"]),
            guild_id=str(data.get("guild_id", "0")),
            name=data["name"],
            race_id=data["race_id"],
            class_id=data["class_id"],
            level=int(data["level"]),
            ruleset_id=data.get("ruleset_id", "dnd5e"),
            ruleset_version=data.get("ruleset_version", "1.0.0"),
            schema_version=data.get("schema_version", "1.0"),
            ability_scores=AbilityScores.from_dict(ability_raw),
            hp_current=data.get("hp_current"),
            hp_max=data.get("hp_max"),
            xp=int(data.get("xp", 0)),
            image_url=data.get("image_url"),
            inventory=list(data.get("inventory", [])),
            choices=normalize_character_choices(dict(data.get("choices", {}))),
        )
