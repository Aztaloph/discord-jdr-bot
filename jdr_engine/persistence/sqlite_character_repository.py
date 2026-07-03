# jdr_engine/persistence/sqlite_character_repository.py
"""Repository SQLite pour les personnages (ÉTAPE 1a)."""
from __future__ import annotations

import logging
from pathlib import Path

from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import (
    get_connection,
    get_db_path,
    row_to_character,
    upsert_character,
)

logger = logging.getLogger(__name__)


class SqliteCharacterRepository:
    """Persistance des personnages dans data/bot.db."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or get_db_path()

    def save(self, character: Character) -> None:
        with get_connection(self.db_path) as conn:
            upsert_character(conn, character)
        logger.info("Personnage SQLite sauvegardé : %s (%s)", character.name, character.id)

    def get_by_id(self, character_id: str) -> Character | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM personnages WHERE id = ?", (character_id,)
            ).fetchone()
        if row is None:
            return None
        return row_to_character(row)

    def get_by_name(
        self,
        name: str,
        owner_id: str,
        guild_id: str | None = None,
    ) -> Character | None:
        owner = str(owner_id)
        name_lower = name.strip().lower()
        query = (
            "SELECT * FROM personnages WHERE discord_user_id = ? AND LOWER(nom) = ?"
        )
        params: list[str] = [owner, name_lower]
        if guild_id is not None:
            query += " AND guild_id = ?"
            params.append(str(guild_id))
        with get_connection(self.db_path) as conn:
            row = conn.execute(query, params).fetchone()
        if row is None:
            return None
        return row_to_character(row)

    def list_by_owner(
        self,
        owner_id: str,
        guild_id: str | None = None,
    ) -> list[Character]:
        owner = str(owner_id)
        query = "SELECT * FROM personnages WHERE discord_user_id = ?"
        params: list[str] = [owner]
        if guild_id is not None:
            query += " AND guild_id = ?"
            params.append(str(guild_id))
        query += " ORDER BY nom COLLATE NOCASE"
        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        return [row_to_character(row) for row in rows]

    def delete(self, character_id: str) -> bool:
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM personnages WHERE id = ?", (character_id,)
            )
            return cursor.rowcount > 0

    def name_exists(
        self,
        name: str,
        owner_id: str,
        exclude_id: str | None = None,
        guild_id: str | None = None,
    ) -> bool:
        existing = self.get_by_name(name, owner_id, guild_id=guild_id)
        if existing is None:
            return False
        if exclude_id and existing.id == exclude_id:
            return False
        return True
