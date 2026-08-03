# tests/unit/test_event_bus.py
"""Lot C0 — EventBus synchrone (ADR-003)."""
from __future__ import annotations

import logging
import unittest
from dataclasses import dataclass
from unittest.mock import patch

from jdr_engine.core.events import DomainEvent, EventBus


@dataclass(frozen=True)
class AlphaEvent(DomainEvent):
    label: str = ""


@dataclass(frozen=True)
class BetaEvent(DomainEvent):
    value: int = 0


class TestEventBusDelivery(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = EventBus()
        self.received: list[DomainEvent] = []

    def test_single_subscriber_receives_event(self) -> None:
        def on_alpha(event: DomainEvent) -> None:
            self.received.append(event)

        self.bus.subscribe(AlphaEvent, on_alpha)
        event = AlphaEvent(label="un")
        self.bus.publish(event)

        self.assertEqual(len(self.received), 1)
        self.assertIs(self.received[0], event)

    def test_multiple_subscribers_all_receive(self) -> None:
        second: list[DomainEvent] = []

        def first_handler(event: DomainEvent) -> None:
            self.received.append(event)

        def second_handler(event: DomainEvent) -> None:
            second.append(event)

        self.bus.subscribe(AlphaEvent, first_handler)
        self.bus.subscribe(AlphaEvent, second_handler)
        event = AlphaEvent(label="deux")
        self.bus.publish(event)

        self.assertEqual(self.received, [event])
        self.assertEqual(second, [event])

    def test_delivery_order_matches_registration_order(self) -> None:
        order: list[str] = []

        def make(name: str):
            def handler(_event: DomainEvent) -> None:
                order.append(name)

            handler.__name__ = name
            return handler

        self.bus.subscribe(AlphaEvent, make("a"))
        self.bus.subscribe(AlphaEvent, make("b"))
        self.bus.subscribe(AlphaEvent, make("c"))
        self.bus.publish(AlphaEvent())

        self.assertEqual(order, ["a", "b", "c"])

    def test_publish_without_subscriber_is_not_an_error(self) -> None:
        self.bus.publish(BetaEvent(value=1))

    def test_unsubscribe_stops_delivery(self) -> None:
        def on_beta(event: DomainEvent) -> None:
            self.received.append(event)

        self.bus.subscribe(BetaEvent, on_beta)
        self.bus.unsubscribe(BetaEvent, on_beta)
        self.bus.publish(BetaEvent(value=3))

        self.assertEqual(self.received, [])

    def test_exact_type_match_only(self) -> None:
        def on_alpha(_event: DomainEvent) -> None:
            self.received.append("alpha")

        self.bus.subscribe(AlphaEvent, on_alpha)
        self.bus.publish(BetaEvent(value=1))

        self.assertEqual(self.received, [])


class TestEventBusFaultIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = EventBus()
        self.received: list[str] = []

    def test_handler_exception_does_not_stop_following_handlers(self) -> None:
        def bad(_event: DomainEvent) -> None:
            raise RuntimeError("handler cassé")

        def good(_event: DomainEvent) -> None:
            self.received.append("ok")

        with patch.object(logging.getLogger("jdr_engine.core.events.bus"), "exception"):
            self.bus.subscribe(AlphaEvent, bad)
            self.bus.subscribe(AlphaEvent, good)
            self.bus.publish(AlphaEvent())

        self.assertEqual(self.received, ["ok"])

    def test_handler_exception_does_not_propagate_to_publisher(self) -> None:
        def bad(_event: DomainEvent) -> None:
            raise ValueError("boom")

        with patch.object(logging.getLogger("jdr_engine.core.events.bus"), "exception"):
            self.bus.subscribe(AlphaEvent, bad)
            self.bus.publish(AlphaEvent(label="safe"))

    def test_handler_exception_is_logged(self) -> None:
        def bad(_event: DomainEvent) -> None:
            raise RuntimeError("journaliser moi")

        with patch.object(
            logging.getLogger("jdr_engine.core.events.bus"), "exception"
        ) as mock_log:
            self.bus.subscribe(AlphaEvent, bad)
            self.bus.publish(AlphaEvent())

        mock_log.assert_called_once()
        args = mock_log.call_args[0]
        self.assertIn("Abonné EventBus en échec", args[0])
        self.assertIn("bad", args[1])
        self.assertIn("AlphaEvent", args[2])


class TestEventBusReentrantPublish(unittest.TestCase):
    def test_nested_publish_delivered_depth_first(self) -> None:
        bus = EventBus()
        trace: list[str] = []

        def on_beta(_event: DomainEvent) -> None:
            trace.append("beta")

        def on_alpha(_event: DomainEvent) -> None:
            trace.append("alpha_start")
            bus.publish(BetaEvent(value=1))
            trace.append("alpha_end")

        def on_alpha_second(_event: DomainEvent) -> None:
            trace.append("alpha_second")

        bus.subscribe(BetaEvent, on_beta)
        bus.subscribe(AlphaEvent, on_alpha)
        bus.subscribe(AlphaEvent, on_alpha_second)
        bus.publish(AlphaEvent(label="root"))

        self.assertEqual(
            trace,
            ["alpha_start", "beta", "alpha_end", "alpha_second"],
        )


if __name__ == "__main__":
    unittest.main()
