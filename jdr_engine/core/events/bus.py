# jdr_engine/core/events/bus.py
"""
EventBus synchrone in-process — ADR-003, lot C0.

Sémantique de publication réentrante
------------------------------------
Si un abonné appelle ``publish`` pendant qu'il traite un événement, la nouvelle
publication est livrée **immédiatement** (depth-first) : tous les abonnés de
l'événement imbriqué sont notifiés avant de reprendre les abonnés restants de
l'événement parent. L'ordre reste déterministe grâce au snapshot des listes
d'abonnés au début de chaque ``publish``.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import TypeVar

from jdr_engine.core.events.domain_event import DomainEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[DomainEvent], None]

E = TypeVar("E", bound=DomainEvent)


def handler_label(handler: EventHandler) -> str:
    """Identifiant stable pour les journaux (nom qualifié ou repr)."""
    qualname = getattr(handler, "__qualname__", None)
    if qualname:
        return qualname
    return repr(handler)


class EventBus:
    """Bus publish/subscribe synchrone — ordre d'enregistrement garanti."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(
            list
        )

    def subscribe(self, event_type: type[E], handler: EventHandler) -> None:
        """Enregistre un abonné pour un type d'événement exact."""
        handlers = self._handlers[event_type]
        if handler not in handlers:
            handlers.append(handler)

    def unsubscribe(self, event_type: type[E], handler: EventHandler) -> None:
        """Retire un abonné ; absent = no-op."""
        handlers = self._handlers.get(event_type)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            return
        if not handlers:
            del self._handlers[event_type]

    def publish(self, event: DomainEvent) -> None:
        """
        Livre l'événement aux abonnés du type exact ``type(event)``.

        Aucune erreur si aucun abonné. Les exceptions des abonnés sont journalisées
        et n'interrompent pas la livraison ni ne remontent à l'appelant.
        """
        event_type = type(event)
        handlers = list(self._handlers.get(event_type, ()))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Abonné EventBus en échec : handler=%s event_type=%s",
                    handler_label(handler),
                    event_type.__name__,
                )

    def handler_count(self, event_type: type[DomainEvent]) -> int:
        """Nombre d'abonnés — utilitaire de test/diagnostic."""
        return len(self._handlers.get(event_type, ()))
