# jdr_engine/application/dto/character_commands.py
from __future__ import annotations

from dataclasses import dataclass, field

from jdr_engine.domain.character.ability_scores import AbilityScores


@dataclass(frozen=True)
class CreateCharacterCommand:
    owner_id: str
    name: str
    race_id: str
    class_id: str
    level: int = 1
    ruleset_id: str = "dnd5e"
    guild_id: str = "0"
    ability_scores: AbilityScores | None = None
    image_url: str | None = None
    hp_current: int | None = None


@dataclass(frozen=True)
class DeleteCharacterCommand:
    character_id: str
    owner_id: str


@dataclass(frozen=True)
class GetCharacterQuery:
    character_id: str | None = None
    name: str | None = None
    owner_id: str = ""


@dataclass(frozen=True)
class ListCharactersQuery:
    owner_id: str
    guild_id: str | None = None


@dataclass(frozen=True)
class GetCharacterSheetQuery:
    character_id: str | None = None
    name: str | None = None
    owner_id: str = ""
    locale: str = "fr"
