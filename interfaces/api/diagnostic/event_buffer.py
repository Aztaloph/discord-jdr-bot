# interfaces/api/diagnostic/event_buffer.py
"""
Tampon circulaire d'événements — diagnostic dev uniquement.

Isolé de ``EventBus`` : la suppression de ce module n'affecte pas le bus.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from jdr_engine.core.events.domain_event import DomainEvent


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {k: _serialize_value(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    return value


def event_to_record(event: DomainEvent) -> dict[str, Any]:
    """Représentation JSON-serializable d'un événement."""
    payload = _serialize_value(event)
    return {
        "type": type(event).__name__,
        "timestamp": event.timestamp.isoformat(),
        "payload": payload,
    }


class EventRingBuffer:
    """Tampon FIFO à taille fixe — éviction des plus anciens."""

    def __init__(self, max_size: int = 500) -> None:
        if max_size < 1:
            raise ValueError("max_size doit être >= 1")
        self._max_size = max_size
        self._entries: deque[dict[str, Any]] = deque(maxlen=max_size)

    def record(self, event: DomainEvent) -> None:
        self._entries.append(event_to_record(event))

    def list_newest_first(self) -> list[dict[str, Any]]:
        return list(reversed(self._entries))

    @property
    def max_size(self) -> int:
        return self._max_size
