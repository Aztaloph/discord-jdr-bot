# interfaces/api/diagnostic/recording_bus.py
"""
Façade EventBus + enregistrement — diagnostic dev uniquement.

Délègue subscribe/unsubscribe/publish au bus interne ; enregistre chaque
``publish`` (y compris réentrant) dans le tampon sans modifier ``EventBus``.
"""
from __future__ import annotations

from collections.abc import Callable

from jdr_engine.core.events.bus import EventBus, EventHandler
from jdr_engine.core.events.domain_event import DomainEvent

from interfaces.api.diagnostic.event_buffer import EventRingBuffer


class RecordingEventBus:
    """Wrapper jetable autour d'un ``EventBus`` existant."""

    def __init__(self, bus: EventBus, buffer: EventRingBuffer) -> None:
        self._bus = bus
        self._buffer = buffer

    @property
    def inner(self) -> EventBus:
        return self._bus

    @property
    def buffer(self) -> EventRingBuffer:
        return self._buffer

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._bus.subscribe(event_type, handler)

    def unsubscribe(
        self, event_type: type[DomainEvent], handler: EventHandler
    ) -> None:
        self._bus.unsubscribe(event_type, handler)

    def publish(self, event: DomainEvent) -> None:
        self._buffer.record(event)
        self._bus.publish(event)
