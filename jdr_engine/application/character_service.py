# jdr_engine/application/character_service.py
"""Use cases CRUD personnages v2 + fiche calculée."""
from __future__ import annotations

import logging

from jdr_engine.application.dto.character_commands import (
    CreateCharacterCommand,
    DeleteCharacterCommand,
    GetCharacterQuery,
    GetCharacterSheetQuery,
    ListCharactersQuery,
)
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.character_sheet import CharacterSheet
from jdr_engine.persistence.character_repository import JsonCharacterRepository
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.engine import RuleEngine

logger = logging.getLogger(__name__)


class CharacterServiceError(Exception):
    """Erreur métier CharacterService."""


class CharacterNotFoundError(CharacterServiceError):
    pass


class CharacterValidationError(CharacterServiceError):
    pass


class CharacterService:
    """Orchestre persistance + Rule Engine pour les personnages."""

    def __init__(
        self,
        repository: JsonCharacterRepository,
        rule_engine: RuleEngine,
    ):
        self._repo = repository
        self._engine = rule_engine

    def create(self, cmd: CreateCharacterCommand) -> Character:
        name = cmd.name.strip()
        if not name:
            raise CharacterValidationError("Le nom du personnage est obligatoire.")
        if not 1 <= cmd.level <= 20:
            raise CharacterValidationError("Le niveau doit être entre 1 et 20.")

        if cmd.ruleset_id != self._engine.ruleset_id:
            raise CharacterValidationError(
                f"Ruleset {cmd.ruleset_id!r} non chargé dans le moteur."
            )
        if not self._engine.entity_exists("race", cmd.race_id):
            raise CharacterValidationError(f"Race inconnue : {cmd.race_id!r}")
        if not self._engine.entity_exists("class", cmd.class_id):
            raise CharacterValidationError(f"Classe inconnue : {cmd.class_id!r}")

        owner = str(cmd.owner_id)
        if self._repo.name_exists(name, owner):
            raise CharacterValidationError(
                f"Vous avez déjà un personnage nommé « {name} »."
            )

        character = Character(
            owner_id=owner,
            name=name,
            race_id=cmd.race_id,
            class_id=cmd.class_id,
            level=cmd.level,
            ruleset_id=cmd.ruleset_id,
            ruleset_version=self._engine.ruleset_version,
            ability_scores=cmd.ability_scores or AbilityScores(),
            hp_current=cmd.hp_current,
            image_url=cmd.image_url,
        )
        self._repo.save(character)
        logger.info("Personnage créé : %s (%s)", character.name, character.id)
        return character

    def _resolve_character(self, query: GetCharacterQuery) -> Character:
        owner = str(query.owner_id)
        character: Character | None = None

        if query.character_id:
            character = self._repo.get_by_id(query.character_id)
        elif query.name:
            character = self._repo.get_by_name(query.name, owner)
        else:
            raise CharacterValidationError("character_id ou name requis.")

        if character is None or character.owner_id != owner:
            raise CharacterNotFoundError("Personnage introuvable.")
        return character

    def get(self, query: GetCharacterQuery) -> Character:
        return self._resolve_character(query)

    def get_sheet(self, query: GetCharacterSheetQuery) -> CharacterSheet:
        char_query = GetCharacterQuery(
            character_id=query.character_id,
            name=query.name,
            owner_id=query.owner_id,
        )
        character = self._resolve_character(char_query)
        return build_character_sheet(
            character,
            self._engine,
            locale=query.locale,
        )

    def list_by_owner(self, query: ListCharactersQuery) -> list[Character]:
        return self._repo.list_by_owner(str(query.owner_id))

    def list_sheets(
        self,
        query: ListCharactersQuery,
        *,
        locale: str = "fr",
    ) -> list[CharacterSheet]:
        return [
            build_character_sheet(c, self._engine, locale=locale)
            for c in self.list_by_owner(query)
        ]

    def delete(self, cmd: DeleteCharacterCommand) -> bool:
        character = self._repo.get_by_id(cmd.character_id)
        if character is None or character.owner_id != str(cmd.owner_id):
            raise CharacterNotFoundError("Personnage introuvable.")
        return self._repo.delete(cmd.character_id)

    def save(self, character: Character) -> Character:
        """Persiste l'état d'un personnage existant (ex. emplacements de sorts)."""
        existing = self._repo.get_by_id(character.id)
        if existing is None:
            raise CharacterNotFoundError("Personnage introuvable.")
        self._repo.save(character)
        return character
