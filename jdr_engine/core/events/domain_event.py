# jdr_engine/core/events/domain_event.py
"""Événements de domaine immuables — base ADR-003."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_event_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class DomainEvent:
    """
    Racine de tous les événements publiés sur l'EventBus.

    Sous-classes par lot (combat, progression, etc.) ajoutent des champs métier.
    """

    event_id: str = field(default_factory=_new_event_id)
    timestamp: datetime = field(default_factory=_utc_now)
    ruleset_id: str = "dnd5e"
    session_id: str | None = None
