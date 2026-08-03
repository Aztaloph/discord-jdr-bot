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


@dataclass(frozen=True, kw_only=True)
class InitiativeRolled(DomainEvent):
    combat_id: str
    guild_id: str
    channel_id: str
    initiative_order: tuple[str, ...]
    rolls: tuple[tuple[str, int, int, int], ...]


@dataclass(frozen=True, kw_only=True)
class TurnStarted(DomainEvent):
    combat_id: str
    guild_id: str
    channel_id: str
    combatant_id: str
    round_number: int
    turn_index: int


@dataclass(frozen=True, kw_only=True)
class TurnEnded(DomainEvent):
    combat_id: str
    guild_id: str
    channel_id: str
    combatant_id: str
    round_number: int
    turn_index: int


@dataclass(frozen=True, kw_only=True)
class RoundStarted(DomainEvent):
    combat_id: str
    guild_id: str
    channel_id: str
    round_number: int
