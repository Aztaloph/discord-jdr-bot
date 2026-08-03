# jdr_engine/core/events/combat_events.py
"""Événements de cycle de vie combat — sous-classes directes de DomainEvent (ADR-003)."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.core.events.domain_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class CombatStarted(DomainEvent):
    combat_id: str
    guild_id: str
    channel_id: str
    character_ids: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class CombatEnded(DomainEvent):
    combat_id: str
    guild_id: str
    channel_id: str
    reason: str = "closed"
