# jdr_engine/persistence/combat_repository.py
"""Persistance SQLite des rencontres — table ``combats`` dans ``data/bot.db``."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.persistence.database import (
    ensure_combats_schema,
    get_connection,
    get_db_path,
)

logger = logging.getLogger(__name__)


class ActiveCombatExistsError(Exception):
    """Un combat actif existe déjà pour ce salon."""


class CombatNotFoundError(Exception):
    """Combat introuvable."""


@dataclass(frozen=True)
class CombatRecord:
    """Ligne SQL + état désérialisé."""

    combat_id: int
    guild_id: str
    channel_id: str
    sql_status: str
    state: CombatState


class SqliteCombatRepository:
    """Repository combats — blob JSON unique par ligne."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_db_path()
        ensure_combats_schema(self.db_path)

    def insert_active(
        self,
        guild_id: str,
        channel_id: str,
        state: CombatState,
    ) -> int:
        if self.get_active_by_channel(guild_id, channel_id) is not None:
            raise ActiveCombatExistsError(
                f"Combat actif déjà présent pour guild={guild_id!r} channel={channel_id!r}."
            )
        payload = json.dumps(state.to_dict(), ensure_ascii=False)
        with get_connection(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO combats (guild_id, channel_id, status, state_json, updated_at)
                    VALUES (?, ?, 'active', ?, datetime('now'))
                    """,
                    (str(guild_id), str(channel_id), payload),
                )
            except sqlite3.IntegrityError as exc:
                raise ActiveCombatExistsError(
                    f"Combat actif déjà présent pour guild={guild_id!r} channel={channel_id!r}."
                ) from exc
            combat_id = int(cursor.lastrowid)
        logger.info(
            "Combat créé : id=%s guild=%s channel=%s",
            combat_id,
            guild_id,
            channel_id,
        )
        return combat_id

    def get_by_id(self, combat_id: int) -> CombatRecord | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM combats WHERE id = ?", (combat_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def get_active_by_channel(
        self,
        guild_id: str,
        channel_id: str,
    ) -> CombatRecord | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM combats
                WHERE guild_id = ? AND channel_id = ? AND status = 'active'
                LIMIT 1
                """,
                (str(guild_id), str(channel_id)),
            ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def save(self, record: CombatRecord) -> None:
        payload = json.dumps(record.state.to_dict(), ensure_ascii=False)
        with get_connection(self.db_path) as conn:
            updated = conn.execute(
                """
                UPDATE combats
                SET status = ?, state_json = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (record.sql_status, payload, record.combat_id),
            ).rowcount
        if updated == 0:
            raise CombatNotFoundError(f"Combat introuvable : id={record.combat_id}.")
        logger.info("Combat sauvegardé : id=%s status=%s", record.combat_id, record.sql_status)


def _row_to_record(row) -> CombatRecord:
    data = json.loads(row["state_json"])
    combat_id = int(row["id"])
    state = CombatState.from_dict(
        data,
        sql_status=str(row["status"]),
        combat_id=str(combat_id),
        guild_id=str(row["guild_id"]),
        channel_id=str(row["channel_id"]),
    )
    return CombatRecord(
        combat_id=combat_id,
        guild_id=str(row["guild_id"]),
        channel_id=str(row["channel_id"]),
        sql_status=str(row["status"]),
        state=state,
    )
