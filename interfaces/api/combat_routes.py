# interfaces/api/combat_routes.py
"""Routes HTTP combat v1 — cycle de vie et actions (contrat §5.2)."""
from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field, model_validator

from interfaces.api.combat_attack import build_weapon_attack_request
from interfaces.api.combat_scope import (
    assert_characters_available_for_combat,
    resolve_create_scope,
)
from interfaces.api.errors import ApiError
from jdr_engine.application.combat_service import CombatService
from jdr_engine.application.dto.output_serializers import (
    attack_roll_resolution_to_dict,
    combat_state_to_dict,
)
from jdr_engine.domain.combat.action_budget import ActionBudgetExhaustedError
from jdr_engine.game.combat_manager import (
    CombatCharacterNotFoundError,
    CombatStatusError,
    CombatantNotFoundError,
    InsufficientCombatantsError,
    NotCombatantTurnError,
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


class AttackRollRequestBody(BaseModel):
    attacker_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    melee_weapon: bool = False
    ranged_weapon: bool = False

    @model_validator(mode="after")
    def _validate_weapon_context(self) -> AttackRollRequestBody:
        if self.melee_weapon == self.ranged_weapon:
            raise ValueError(
                "Indiquer melee_weapon ou ranged_weapon (exclusifs)."
            )
        return self


def register_combat_routes(
    app: FastAPI,
    *,
    combat_service: CombatService,
    character_repository: SqliteCharacterRepository,
    combat_repository: SqliteCombatRepository,
    engine,
    locale: str = "fr",
    initiative_rng: Callable[[], int] | None = None,
    attack_rng=None,
) -> None:
    """Enregistre ``/v1/combats/…`` sur l'application."""
    app.state.combat_initiative_rng = initiative_rng
    app.state.combat_attack_rng = attack_rng

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
    def activate_combat(combat_id: int, request: Request) -> dict:
        rng = getattr(request.app.state, "combat_initiative_rng", None)
        try:
            state = combat_service.activate_combat(combat_id, rng=rng)
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

    @app.post("/v1/combats/{combat_id}/attack-roll")
    def attack_roll(
        combat_id: int,
        body: AttackRollRequestBody,
        request: Request,
    ) -> dict:
        try:
            state = combat_service.load_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

        if body.attacker_id not in state.combatants:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                "Combattant introuvable.",
                details={"combatant_id": body.attacker_id},
            )
        if body.target_id not in state.combatants:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                "Combattant introuvable.",
                details={"combatant_id": body.target_id},
            )

        attacker_combatant = state.combatants[body.attacker_id]
        character = character_repository.get_by_id(attacker_combatant.character_id)
        if character is None:
            raise ApiError(
                404,
                "CHARACTER_NOT_FOUND",
                "Personnage introuvable.",
                details={"character_id": attacker_combatant.character_id},
            )

        roll_request = build_weapon_attack_request(
            character,
            engine,
            melee_weapon=body.melee_weapon,
            ranged_weapon=body.ranged_weapon,
            locale=locale,
        )
        rng = getattr(request.app.state, "combat_attack_rng", None)
        try:
            resolution = combat_service.resolve_attack_roll(
                combat_id,
                body.attacker_id,
                body.target_id,
                roll_request,
                rng=rng,
            )
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        except CombatantNotFoundError as exc:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                str(exc),
            ) from exc
        except ActionBudgetExhaustedError as exc:
            raise ApiError(
                409,
                "ACTION_BUDGET_EXHAUSTED",
                str(exc),
            ) from exc
        except NotCombatantTurnError as exc:
            raise ApiError(
                409,
                "NOT_COMBATANT_TURN",
                str(exc),
            ) from exc
        except CombatStatusError as exc:
            raise ApiError(
                409,
                "COMBAT_STATUS_INVALID",
                str(exc),
            ) from exc
        except CombatCharacterNotFoundError as exc:
            raise ApiError(
                404,
                "CHARACTER_NOT_FOUND",
                str(exc),
            ) from exc
        return attack_roll_resolution_to_dict(resolution)

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
