# jdr_engine/core/events/handlers/combat_auto_save.py
"""Journal append-only des événements combat — lot C7 (ADR-003)."""
from __future__ import annotations

from jdr_engine.core.events.bus import EventBus
from jdr_engine.core.events.combat_events import (
    ActionConsumed,
    AttackRollResolved,
    CombatEnded,
    CombatStarted,
    ConcentrationBroken,
    ConditionApplied,
    ConditionRemoved,
    DamageDealt,
    InitiativeRolled,
    RoundStarted,
    SavingThrowResolved,
    SpellCast,
    TurnEnded,
    TurnStarted,
)
from jdr_engine.core.events.domain_event import DomainEvent
from jdr_engine.persistence.combat_log_repository import SqliteCombatLogRepository

COMBAT_EVENT_TYPES: tuple[type[DomainEvent], ...] = (
    CombatStarted,
    CombatEnded,
    InitiativeRolled,
    TurnStarted,
    TurnEnded,
    RoundStarted,
    AttackRollResolved,
    DamageDealt,
    SpellCast,
    SavingThrowResolved,
    ConditionApplied,
    ConditionRemoved,
    ConcentrationBroken,
    ActionConsumed,
)


class CombatAutoSaveHandler:
    """
    Append les événements combat publiés dans le journal SQLite.

    Ne remplace pas ``CombatManager._persist()`` — l'état est déjà sauvegardé
    de façon synchrone avant publication (C1–C6).
    """

    def __init__(self, log_repository: SqliteCombatLogRepository) -> None:
        self._log = log_repository

    def register(self, event_bus: EventBus) -> None:
        for event_type in COMBAT_EVENT_TYPES:
            event_bus.subscribe(event_type, self.handle)

    def handle(self, event: DomainEvent) -> None:
        combat_id = getattr(event, "combat_id", None)
        if combat_id is None:
            return
        self._log.append(int(combat_id), event)
