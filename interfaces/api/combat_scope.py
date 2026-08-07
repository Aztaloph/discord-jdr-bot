# interfaces/api/combat_scope.py
"""Scope de création combat API — guild/channel et invariant lobby (contrat §2.5, §10)."""
from __future__ import annotations

import uuid

from interfaces.api.errors import ApiError
from jdr_engine.persistence.combat_repository import SqliteCombatRepository

DEFAULT_API_GUILD_ID = "api"
GENERATED_CHANNEL_ID_PREFIX = "api-gen-"


def resolve_create_scope(
    *,
    guild_id: str | None,
    channel_id: str | None,
) -> tuple[str, str]:
    """
    Projette le body client vers le scope persistence.

    ``channel_id`` absent → UUID préfixé ``api-gen-`` (pas de collision avec un id
    client fourni sans ce préfixe).
    """
    resolved_guild = guild_id or DEFAULT_API_GUILD_ID
    if channel_id is not None:
        resolved_channel = channel_id
    else:
        resolved_channel = f"{GENERATED_CHANNEL_ID_PREFIX}{uuid.uuid4()}"
    return resolved_guild, resolved_channel


def find_open_combat_for_character(
    combat_repository: SqliteCombatRepository,
    character_id: str,
) -> int | None:
    """Retourne l'id du combat ouvert contenant ``character_id``, ou ``None``."""
    for record in combat_repository.list_open():
        for combatant in record.state.combatants.values():
            if combatant.character_id == character_id:
                return record.combat_id
    return None


def assert_characters_available_for_combat(
    combat_repository: SqliteCombatRepository,
    character_ids: list[str],
) -> None:
    """Invariant lobby — aucun personnage déjà engagé dans un combat ouvert."""
    for character_id in character_ids:
        combat_id = find_open_combat_for_character(
            combat_repository,
            character_id,
        )
        if combat_id is not None:
            raise ApiError(
                409,
                "CHARACTER_ALREADY_IN_COMBAT",
                (
                    f"Le personnage {character_id!r} participe déjà "
                    f"au combat {combat_id}."
                ),
                details={
                    "character_id": character_id,
                    "combat_id": combat_id,
                },
            )
