# jdr_engine/game/combat_manager.py
"""Orchestration de rencontre — lots C1 (cycle de vie) et C2 (initiative, tours)."""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Callable

from jdr_engine.core.events.bus import EventBus
from jdr_engine.core.events.combat_events import (
    CombatEnded,
    CombatStarted,
    InitiativeRolled,
    RoundStarted,
    TurnEnded,
    TurnStarted,
)
from jdr_engine.domain.combat.combat_state import (
    COMBAT_STATE_VERSION,
    CombatState,
    sql_status_from_combat,
    utc_now_iso,
)
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.persistence.combat_repository import (
    CombatNotFoundError,
    CombatRecord,
    OpenCombatExistsError,
    SqliteCombatRepository,
)
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.combat.initiative import (
    InitiativeRollResult,
    next_active_turn_index,
    roll_initiative,
    sort_initiative_order,
)
from jdr_engine.rules.engine import RuleEngine

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Alias rétrocompatibilité.
ActiveCombatExistsError = OpenCombatExistsError


class CombatCharacterNotFoundError(Exception):
    """Personnage requis pour le combat introuvable."""


class CombatStatusError(Exception):
    """Opération interdite pour le statut courant du combat."""


class InsufficientCombatantsError(Exception):
    """Nombre de combattants insuffisant pour l'opération."""


class NoActiveCombatantsError(Exception):
    """Aucun combattant actif dans la séquence d'initiative."""


class CombatManager:
    """
    Machine de cycle de vie combat — création, initiative, tours (C2).

    Publie les événements de cycle sur l'EventBus injecté.
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
        character_ids: list[str] | None = None,
    ) -> CombatState:
        """Ouvre un combat en ``preparing`` ; publie ``CombatStarted``."""
        combatants: dict[str, Combatant] = {}
        resolved_character_ids: list[str] = []

        for character_id in character_ids or []:
            combatant = self._build_combatant(character_id)
            combatants[combatant.combatant_id] = combatant
            resolved_character_ids.append(character_id)

        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id=self._engine.ruleset_id,
            round_number=0,
            turn_index=0,
            initiative_order=(),
            combatants=combatants,
            status="preparing",
            started_at=utc_now_iso(),
            guild_id=str(guild_id),
            channel_id=str(channel_id),
        )

        combat_id = self._combats.insert(guild_id, channel_id, state)
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

    def add_combatant(self, combat_id: int, character_id: str) -> CombatState:
        """Ajoute un PJ pendant ``preparing`` uniquement."""
        state = self._require_state(combat_id)
        if state.status != "preparing":
            raise CombatStatusError(
                "Les combattants ne peuvent être ajoutés qu'en préparation."
            )
        combatant = self._build_combatant(character_id)
        state.combatants[combatant.combatant_id] = combatant
        self._persist(state)
        return state

    def activate_combat(
        self,
        combat_id: int,
        *,
        rng: Callable[[], int] | None = None,
    ) -> CombatState:
        """
        Passe en ``active``, calcule l'initiative (ordre figé), démarre le tour 1.

        Requiert au moins deux combattants actifs.
        """
        state = self._require_state(combat_id)
        if state.status != "preparing":
            raise CombatStatusError(
                "Seul un combat en préparation peut être activé."
            )
        active = [c for c in state.combatants.values() if c.is_active]
        if len(active) < 2:
            raise InsufficientCombatantsError(
                "Au moins deux combattants sont requis pour activer le combat."
            )

        rolls = self._roll_initiative_for_combatants(active, rng=rng)
        order = sort_initiative_order(rolls)
        roll_by_id = {r.combatant_id: r for r in rolls}

        updated_combatants = dict(state.combatants)
        for combatant_id, roll in roll_by_id.items():
            old = updated_combatants[combatant_id]
            updated_combatants[combatant_id] = Combatant(
                combatant_id=old.combatant_id,
                display_name=old.display_name,
                kind=old.kind,
                character_id=old.character_id,
                is_active=old.is_active,
                initiative_total=roll.total,
            )

        state.combatants = updated_combatants
        state.initiative_order = order
        state.status = "active"
        state.round_number = 1
        state.turn_index = 0
        self._persist(state)

        record = self._combats.get_by_id(combat_id)
        assert record is not None
        self._publish_initiative_events(record, rolls, order)
        self._publish_turn_started(state)
        return state

    def advance_turn(self, combat_id: int) -> CombatState:
        """Termine le tour courant et démarre le suivant (combattants inactifs ignorés)."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError(
                "L'avancement de tour n'est possible qu'en combat actif."
            )
        if not state.initiative_order:
            raise CombatStatusError("Aucune séquence d'initiative établie.")

        current_id = state.initiative_order[state.turn_index]
        self._bus.publish(
            TurnEnded(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=current_id,
                round_number=state.round_number,
                turn_index=state.turn_index,
            )
        )

        def _is_active(combatant_id: str) -> bool:
            return state.combatants[combatant_id].is_active

        result = next_active_turn_index(
            state.initiative_order,
            state.turn_index,
            is_active=_is_active,
        )
        if result is None:
            raise NoActiveCombatantsError(
                "Aucun combattant actif — fin de combat non tranchée (ambiguïté C2)."
            )

        new_index, delta_round = result
        if delta_round:
            state.round_number += 1
            self._bus.publish(
                RoundStarted(
                    ruleset_id=state.ruleset_id,
                    combat_id=state.combat_id or str(combat_id),
                    guild_id=state.guild_id or "",
                    channel_id=state.channel_id or "",
                    round_number=state.round_number,
                )
            )
        state.turn_index = new_index
        self._persist(state)
        self._publish_turn_started(state)
        return state

    def remove_combatant(self, combat_id: int, combatant_id: str) -> CombatState:
        """Marque un combattant inactif ; conserve sa place dans l'initiative."""
        state = self._require_state(combat_id)
        if state.status == "ended":
            raise CombatStatusError("Combat déjà terminé.")
        if combatant_id not in state.combatants:
            raise ValueError(f"Combattant introuvable : {combatant_id!r}.")
        old = state.combatants[combatant_id]
        state.combatants[combatant_id] = Combatant(
            combatant_id=old.combatant_id,
            display_name=old.display_name,
            kind=old.kind,
            character_id=old.character_id,
            is_active=False,
            initiative_total=old.initiative_total,
        )
        self._persist(state)
        return state

    def load_combat(self, combat_id: int) -> CombatState:
        """Charge un combat par identifiant SQL."""
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        return record.state

    def load_open_combat(
        self,
        guild_id: str,
        channel_id: str,
    ) -> CombatState | None:
        """Retourne le combat ouvert (preparing ou active) du salon, ou ``None``."""
        record = self._combats.get_open_by_channel(guild_id, channel_id)
        if record is None:
            return None
        return record.state

    def load_active_combat(
        self,
        guild_id: str,
        channel_id: str,
    ) -> CombatState | None:
        """Alias C1 — combat ouvert (preparing ou active)."""
        return self.load_open_combat(guild_id, channel_id)

    def save_combat(self, state: CombatState) -> None:
        """Persiste l'état complet du combat (blob JSON)."""
        if state.combat_id is None:
            raise ValueError("combat_id requis pour sauvegarder.")
        combat_id = int(state.combat_id)
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        sql_status = sql_status_from_combat(state.status)
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
        """Clôture un combat ouvert ; publie ``CombatEnded``."""
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

    def _build_combatant(self, character_id: str) -> Combatant:
        character = self._characters.get_by_id(character_id)
        if character is None:
            raise CombatCharacterNotFoundError(
                f"Personnage introuvable pour le combat : {character_id!r}."
            )
        sheet = build_character_sheet(character, self._engine)
        combatant_id = str(uuid.uuid4())[:8]
        return Combatant(
            combatant_id=combatant_id,
            display_name=sheet.name,
            kind="player_character",
            character_id=character_id,
        )

    def _roll_initiative_for_combatants(
        self,
        combatants: list[Combatant],
        *,
        rng: Callable[[], int] | None,
    ) -> list[InitiativeRollResult]:
        rolls: list[InitiativeRollResult] = []
        for combatant in combatants:
            character = self._characters.get_by_id(combatant.character_id)
            if character is None:
                raise CombatCharacterNotFoundError(
                    f"Personnage introuvable : {combatant.character_id!r}."
                )
            sheet = build_character_sheet(character, self._engine)
            rolls.append(
                roll_initiative(combatant.combatant_id, sheet.initiative, rng=rng)
            )
        return rolls

    def _require_state(self, combat_id: int) -> CombatState:
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        return record.state

    def _persist(self, state: CombatState) -> None:
        if state.combat_id is None:
            raise ValueError("combat_id requis pour persister.")
        combat_id = int(state.combat_id)
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        self._combats.save(
            CombatRecord(
                combat_id=combat_id,
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                sql_status=sql_status_from_combat(state.status),
                state=state,
            )
        )

    def _publish_initiative_events(
        self,
        record: CombatRecord,
        rolls: list[InitiativeRollResult],
        order: tuple[str, ...],
    ) -> None:
        state = record.state
        roll_payload = tuple(
            (r.combatant_id, r.d20, r.modifier, r.total) for r in rolls
        )
        self._bus.publish(
            InitiativeRolled(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(record.combat_id),
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                initiative_order=order,
                rolls=roll_payload,
            )
        )

    def _publish_turn_started(self, state: CombatState) -> None:
        combatant_id = state.initiative_order[state.turn_index]
        self._bus.publish(
            TurnStarted(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or "",
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=combatant_id,
                round_number=state.round_number,
                turn_index=state.turn_index,
            )
        )
