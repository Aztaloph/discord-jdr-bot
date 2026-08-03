# jdr_engine/game/combat_manager.py
"""Orchestration de rencontre — lot C1 (création, chargement, sauvegarde, clôture)."""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from jdr_engine.core.events.bus import EventBus
from jdr_engine.core.events.combat_events import CombatEnded, CombatStarted
from jdr_engine.domain.combat.combat_state import (
    COMBAT_STATE_VERSION,
    CombatState,
    utc_now_iso,
)
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.persistence.combat_repository import (
    ActiveCombatExistsError,
    CombatNotFoundError,
    CombatRecord,
    SqliteCombatRepository,
)
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.engine import RuleEngine

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CombatCharacterNotFoundError(Exception):
    """Personnage requis pour créer un combat introuvable."""


class CombatManager:
    """
    Machine de cycle de vie combat — sans initiative, tours ni attaques (C2+).

    Publie ``CombatStarted`` / ``CombatEnded`` sur l'EventBus injecté.
    """

    def __init__(
        self,
        event_bus: EventBus,
        combat_repository: SqliteCombatRepository,
        character_repository: SqliteCharacterRepository,
        engine: RuleEngine,
    ) -> None:
        self._bus = event_bus
        self._combats = combat_repository
        self._characters = character_repository
        self._engine = engine

    def create_combat(
        self,
        guild_id: str,
        channel_id: str,
        character_ids: list[str],
    ) -> CombatState:
        """Crée un combat actif avec les PJ indiqués ; publie ``CombatStarted``."""
        if not character_ids:
            raise ValueError("Au moins un personnage est requis pour créer un combat.")

        combatants: dict[str, Combatant] = {}
        resolved_character_ids: list[str] = []

        for character_id in character_ids:
            character = self._characters.get_by_id(character_id)
            if character is None:
                raise CombatCharacterNotFoundError(
                    f"Personnage introuvable pour le combat : {character_id!r}."
                )
            sheet = build_character_sheet(character, self._engine)
            combatant_id = str(uuid.uuid4())[:8]
            combatants[combatant_id] = Combatant(
                combatant_id=combatant_id,
                display_name=sheet.name,
                kind="player_character",
                character_id=character_id,
            )
            resolved_character_ids.append(character_id)

        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id=self._engine.ruleset_id,
            round_number=1,
            turn_index=0,
            initiative_order=(),
            combatants=combatants,
            status="active",
            started_at=utc_now_iso(),
            guild_id=str(guild_id),
            channel_id=str(channel_id),
        )

        combat_id = self._combats.insert_active(guild_id, channel_id, state)
        state.combat_id = str(combat_id)

        self._bus.publish(
            CombatStarted(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id,
                guild_id=str(guild_id),
                channel_id=str(channel_id),
                character_ids=tuple(resolved_character_ids),
            )
        )
        return state

    def load_combat(self, combat_id: int) -> CombatState:
        """Charge un combat par identifiant SQL."""
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        return record.state

    def load_active_combat(
        self,
        guild_id: str,
        channel_id: str,
    ) -> CombatState | None:
        """Retourne le combat actif du salon, ou ``None``."""
        record = self._combats.get_active_by_channel(guild_id, channel_id)
        if record is None:
            return None
        return record.state

    def save_combat(self, state: CombatState) -> None:
        """Persiste l'état complet du combat (blob JSON)."""
        if state.combat_id is None:
            raise ValueError("combat_id requis pour sauvegarder.")
        combat_id = int(state.combat_id)
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        sql_status = "active" if state.status == "active" else "ended"
        if state.status not in ("active", "ended"):
            sql_status = record.sql_status
        self._combats.save(
            CombatRecord(
                combat_id=combat_id,
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                sql_status=sql_status,
                state=state,
            )
        )

    def close_combat(self, combat_id: int, *, reason: str = "closed") -> CombatState:
        """Clôture un combat actif ; publie ``CombatEnded``."""
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        if record.state.status == "ended":
            return record.state

        state = record.state
        state.status = "ended"
        state.ended_at = utc_now_iso()

        self._combats.save(
            CombatRecord(
                combat_id=record.combat_id,
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                sql_status="ended",
                state=state,
            )
        )

        self._bus.publish(
            CombatEnded(
                ruleset_id=state.ruleset_id,
                combat_id=str(combat_id),
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                reason=reason,
            )
        )
        return state
