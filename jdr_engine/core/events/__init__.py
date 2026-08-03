# jdr_engine/core/events/ — EventBus in-process (ADR-003, lot C0).
from jdr_engine.core.events.bus import EventBus, EventHandler, handler_label
from jdr_engine.core.events.domain_event import DomainEvent

__all__ = [
    "DomainEvent",
    "EventBus",
    "EventHandler",
    "handler_label",
]
