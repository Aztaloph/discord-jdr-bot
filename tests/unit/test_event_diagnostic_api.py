# tests/unit/test_event_diagnostic_api.py
"""Lot C0 — page et endpoint de diagnostic des événements."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from jdr_engine.core.events import DomainEvent
from jdr_engine.persistence.database import init_database
from jdr_engine.rules import RuleEngine

from interfaces.api.app import create_app
from interfaces.api.diagnostic.event_buffer import EventRingBuffer
from interfaces.api.diagnostic.recording_bus import RecordingEventBus
from jdr_engine.core.events.bus import EventBus


@dataclass(frozen=True)
class ProbeEvent(DomainEvent):
    note: str = ""


class TestEventDiagnosticApi(unittest.TestCase):
    def setUp(self) -> None:
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        self._tmpdir = tempfile.TemporaryDirectory()
        db = init_database(Path(self._tmpdir.name) / "bot.db")
        engine = RuleEngine.load("dnd5e", validate=True, strict=True)
        inner = EventBus()
        buffer = EventRingBuffer(max_size=10)
        bus = RecordingEventBus(inner, buffer)
        self.app = create_app(engine=engine, db_path=db, event_bus=bus)
        self.client = TestClient(self.app)
        self.bus = bus

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_debug_events_empty_at_start(self) -> None:
        response = self.client.get("/debug/events")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_debug_events_lists_published_event(self) -> None:
        self.bus.publish(ProbeEvent(note="ping"))
        response = self.client.get("/debug/events")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["type"], "ProbeEvent")
        self.assertEqual(data[0]["payload"]["note"], "ping")
        self.assertIn("timestamp", data[0])

    def test_debug_events_view_returns_html(self) -> None:
        response = self.client.get("/debug/events/view")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("Flux d'événements", response.text)


if __name__ == "__main__":
    unittest.main()
