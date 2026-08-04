# jdr_engine/core/events/event_serialization.py
"""Sérialisation JSON des événements de domaine — lot C7 (journal combat)."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from jdr_engine.core.events.domain_event import DomainEvent


def domain_event_to_dict(event: DomainEvent) -> dict[str, Any]:
    """Convertit un ``DomainEvent`` en dict JSON-serialisable."""
    payload = asdict(event)
    timestamp = payload.get("timestamp")
    if isinstance(timestamp, datetime):
        payload["timestamp"] = timestamp.isoformat()
    payload["event_type"] = type(event).__name__
    return payload
