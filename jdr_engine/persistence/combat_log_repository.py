# jdr_engine/persistence/combat_log_repository.py
"""Journal append-only des événements combat — lot C7."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jdr_engine.core.events.domain_event import DomainEvent
from jdr_engine.core.events.event_serialization import domain_event_to_dict
from jdr_engine.persistence.database import ensure_combat_log_schema, get_connection, get_db_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CombatLogEntry:
    """Ligne du journal d'événements combat."""

    log_id: int
    combat_id: int
    event_type: str
    payload: dict
    created_at: str


class SqliteCombatLogRepository:
    """Repository append-only — table ``combat_event_log``."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_db_path()
        ensure_combat_log_schema(self.db_path)

    def append(self, combat_id: int, event: DomainEvent) -> int:
        payload = domain_event_to_dict(event)
        event_type = str(payload.get("event_type", type(event).__name__))
        created_at = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload, ensure_ascii=False)
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO combat_event_log (combat_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (combat_id, event_type, payload_json, created_at),
            )
            log_id = int(cursor.lastrowid)
        logger.debug(
            "Journal combat : combat_id=%s event_type=%s log_id=%s",
            combat_id,
            event_type,
            log_id,
        )
        return log_id

    def list_for_combat(self, combat_id: int) -> list[CombatLogEntry]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, combat_id, event_type, payload_json, created_at
                FROM combat_event_log
                WHERE combat_id = ?
                ORDER BY id ASC
                """,
                (combat_id,),
            ).fetchall()
        entries: list[CombatLogEntry] = []
        for row in rows:
            entries.append(
                CombatLogEntry(
                    log_id=int(row["id"]),
                    combat_id=int(row["combat_id"]),
                    event_type=str(row["event_type"]),
                    payload=json.loads(row["payload_json"]),
                    created_at=str(row["created_at"]),
                )
            )
        return entries
