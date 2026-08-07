# interfaces/api/combat_routes.py
"""Routes HTTP combat v1 — cycle de vie (contrat §5.2, lot 1 commit 3)."""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from interfaces.api.combat_scope import (
    assert_characters_available_for_combat,
    resolve_create_scope,
)
from interfaces.api.errors import ApiError
from jdr_engine.application.combat_service import CombatService
from jdr_engine.application.dto.output_serializers import combat_state_to_dict
from jdr_engine.game.combat_manager import (
    CombatCharacterNotFoundError,
    CombatStatusError,
    InsufficientCombatantsError,
)
from jdr_engine.persistence.combat_repository import (
    CombatNotFoundError,
    OpenCombatExistsError,
    SqliteCombatRepository,
)
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)


class CreateCombatRequest(BaseModel):
    character_ids: list[str] = Field(min_length=1)
    channel_id: str | None = None
    guild_id: str | None = None


def register_combat_routes(
    app: FastAPI,
    *,
    combat_service: CombatService,
    character_repository: SqliteCharacterRepository,
    combat_repository: SqliteCombatRepository,
) -> None:
    """Enregistre ``POST/GET /v1/combats/…`` sur l'application."""

    def _assert_characters_exist(character_ids: list[str]) -> None:
        for character_id in character_ids:
            if character_repository.get_by_id(character_id) is None:
                raise ApiError(
                    404,
                    "CHARACTER_NOT_FOUND",
                    "Personnage introuvable.",
                    details={"character_id": character_id},
                )

    def _combat_response(combat_id: int) -> dict:
        state = combat_service.load_combat(combat_id)
        return combat_state_to_dict(state)

    @app.post("/v1/combats")
    def create_combat(body: CreateCombatRequest) -> dict:
        _assert_characters_exist(body.character_ids)
        assert_characters_available_for_combat(
            combat_repository,
            body.character_ids,
        )
        guild_id, channel_id = resolve_create_scope(
            guild_id=body.guild_id,
            channel_id=body.channel_id,
        )
        try:
            state = combat_service.create_combat(
                guild_id,
                channel_id,
                body.character_ids,
            )
        except CombatCharacterNotFoundError as exc:
            raise ApiError(
                404,
                "CHARACTER_NOT_FOUND",
                str(exc),
            ) from exc
        except OpenCombatExistsError as exc:
            raise ApiError(
                409,
                "OPEN_COMBAT_EXISTS",
                str(exc),
            ) from exc
        return combat_state_to_dict(state)

    @app.get("/v1/combats/{combat_id}")
    def get_combat(combat_id: int) -> dict:
        try:
            return _combat_response(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

    @app.post("/v1/combats/{combat_id}/activate")
    def activate_combat(combat_id: int) -> dict:
        try:
            state = combat_service.activate_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        except InsufficientCombatantsError as exc:
            raise ApiError(
                409,
                "INSUFFICIENT_COMBATANTS",
                str(exc),
            ) from exc
        except CombatStatusError as exc:
            raise ApiError(
                409,
                "COMBAT_STATUS_INVALID",
                str(exc),
            ) from exc
        return combat_state_to_dict(state)

    @app.post("/v1/combats/{combat_id}/close")
    def close_combat(combat_id: int) -> dict:
        try:
            state = combat_service.close_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        return combat_state_to_dict(state)
