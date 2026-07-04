# jdr_engine/persistence/database.py
"""
Accès centralisé SQLite — une base par instance de bot (data/bot.db).

Tout SQL passe par ce module ; les repositories n'exécutent que via get_connection().
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from jdr_engine.compendium.paths import get_project_root
from jdr_engine.domain.character.choices_schema import normalize_character_choices
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.character_repository import (
    get_v2_characters_path,
)

logger = logging.getLogger(__name__)

DB_SCHEMA_VERSION = 1
DEFAULT_DB_PATH = get_project_root() / "data" / "bot.db"

# Marqueurs one-shot — SQLite est la source de vérité après le premier import.
META_JSON_V2_IMPORT_DONE = "json_v2_import_done"
META_FIXTURES_IMPORT_DONE = "fixtures_import_done"

_CREATE_PERSONNAGES = """
CREATE TABLE IF NOT EXISTS personnages (
    id TEXT PRIMARY KEY,
    discord_user_id TEXT NOT NULL,
    guild_id TEXT NOT NULL DEFAULT '0',
    nom TEXT NOT NULL,
    race_id TEXT NOT NULL DEFAULT 'human',
    classe TEXT NOT NULL,
    niveau INTEGER NOT NULL,
    force INTEGER NOT NULL DEFAULT 10,
    dex INTEGER NOT NULL DEFAULT 10,
    con INTEGER NOT NULL DEFAULT 10,
    int_score INTEGER NOT NULL DEFAULT 10,
    sag INTEGER NOT NULL DEFAULT 10,
    cha INTEGER NOT NULL DEFAULT 10,
    pv_actuels INTEGER,
    pv_max INTEGER,
    emplacements_sorts TEXT NOT NULL DEFAULT '{}',
    specialisation TEXT,
    inventaire TEXT NOT NULL DEFAULT '[]',
    choices TEXT NOT NULL DEFAULT '{}',
    ruleset_id TEXT NOT NULL DEFAULT 'dnd5e',
    ruleset_version TEXT NOT NULL DEFAULT '1.0.0',
    schema_version TEXT NOT NULL DEFAULT '1.0',
    xp INTEGER NOT NULL DEFAULT 0,
    image_url TEXT,
    extra TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);
"""

_CREATE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_personnages_owner_guild_nom
    ON personnages (discord_user_id, guild_id, nom COLLATE NOCASE);
"""

_CREATE_META = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_CREATE_PERSO_ACTIF = """
CREATE TABLE IF NOT EXISTS perso_actif (
    discord_user_id TEXT NOT NULL,
    guild_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (discord_user_id, guild_id)
);
"""


def get_db_path() -> Path:
    return DEFAULT_DB_PATH


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_schema_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = ?", (key,)
    ).fetchone()
    return str(row["value"]) if row else None


def set_schema_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


def is_one_shot_import_done(conn: sqlite3.Connection, key: str) -> bool:
    return get_schema_meta(conn, key) == "1"


def mark_one_shot_import_done(conn: sqlite3.Connection, key: str) -> None:
    set_schema_meta(conn, key, "1")


def init_database(db_path: Path | None = None) -> Path:
    """Crée le schéma si absent. Retourne le chemin de la base."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        conn.executescript(_CREATE_META)
        conn.executescript(_CREATE_PERSONNAGES)
        conn.executescript(_CREATE_INDEX)
        conn.executescript(_CREATE_PERSO_ACTIF)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(DB_SCHEMA_VERSION)),
        )
    logger.info("Base SQLite initialisée : %s (schéma v%d)", path, DB_SCHEMA_VERSION)
    return path


def _extract_spell_slots(choices: dict[str, Any]) -> dict[str, int]:
    spellcasting = choices.get("spellcasting")
    if not isinstance(spellcasting, dict):
        return {}
    used = spellcasting.get("slots_used") or {}
    if not isinstance(used, dict):
        return {}
    return {str(k): int(v) for k, v in used.items()}


def _merge_spell_slots_into_choices(
    choices: dict[str, Any],
    emplacements_sorts: dict[str, int],
) -> dict[str, Any]:
    merged = dict(choices)
    spellcasting = dict(merged.get("spellcasting") or {})
    if emplacements_sorts:
        spellcasting["slots_used"] = emplacements_sorts
    if spellcasting:
        merged["spellcasting"] = spellcasting
    return merged


def character_to_row(character: Character) -> dict[str, Any]:
    scores = character.ability_scores.to_dict()
    choices = normalize_character_choices(dict(character.choices or {}))
    emplacements = _extract_spell_slots(choices)
    specialization = choices.get("specialization") or choices.get("subclass")
    if isinstance(specialization, dict):
        specialization = specialization.get("id")
    return {
        "id": character.id,
        "discord_user_id": str(character.owner_id),
        "guild_id": str(character.guild_id or "0"),
        "nom": character.name,
        "race_id": character.race_id,
        "classe": character.class_id,
        "niveau": character.level,
        "force": int(scores.get("str", 10)),
        "dex": int(scores.get("dex", 10)),
        "con": int(scores.get("con", 10)),
        "int_score": int(scores.get("int", 10)),
        "sag": int(scores.get("wis", 10)),
        "cha": int(scores.get("cha", 10)),
        "pv_actuels": character.hp_current,
        "pv_max": character.hp_max,
        "emplacements_sorts": json.dumps(emplacements, ensure_ascii=False),
        "specialisation": specialization,
        "inventaire": json.dumps(list(character.inventory), ensure_ascii=False),
        "choices": json.dumps(choices, ensure_ascii=False),
        "ruleset_id": character.ruleset_id,
        "ruleset_version": character.ruleset_version,
        "schema_version": character.schema_version,
        "xp": character.xp,
        "image_url": character.image_url,
        "extra": json.dumps({}, ensure_ascii=False),
        "updated_at": _utc_now(),
    }


def row_to_character(row: sqlite3.Row) -> Character:
    choices = normalize_character_choices(json.loads(row["choices"] or "{}"))
    emplacements = json.loads(row["emplacements_sorts"] or "{}")
    if emplacements:
        choices = _merge_spell_slots_into_choices(choices, emplacements)
    if row["specialisation"]:
        choices.setdefault("specialization", row["specialisation"])
    data = {
        "id": row["id"],
        "owner_id": row["discord_user_id"],
        "guild_id": row["guild_id"],
        "name": row["nom"],
        "race_id": row["race_id"],
        "class_id": row["classe"],
        "level": row["niveau"],
        "ruleset_id": row["ruleset_id"],
        "ruleset_version": row["ruleset_version"],
        "schema_version": row["schema_version"],
        "ability_scores": {
            "str": row["force"],
            "dex": row["dex"],
            "con": row["con"],
            "int": row["int_score"],
            "wis": row["sag"],
            "cha": row["cha"],
        },
        "hp_current": row["pv_actuels"],
        "hp_max": row["pv_max"],
        "xp": row["xp"],
        "image_url": row["image_url"],
        "inventory": json.loads(row["inventaire"] or "[]"),
        "choices": choices,
    }
    char = Character.from_dict(data)
    return char


def upsert_character(conn: sqlite3.Connection, character: Character) -> None:
    row = character_to_row(character)
    conn.execute(
        """
        INSERT INTO personnages (
            id, discord_user_id, guild_id, nom, race_id, classe, niveau,
            force, dex, con, int_score, sag, cha,
            pv_actuels, pv_max, emplacements_sorts, specialisation,
            inventaire, choices, ruleset_id, ruleset_version, schema_version,
            xp, image_url, extra, updated_at
        ) VALUES (
            :id, :discord_user_id, :guild_id, :nom, :race_id, :classe, :niveau,
            :force, :dex, :con, :int_score, :sag, :cha,
            :pv_actuels, :pv_max, :emplacements_sorts, :specialisation,
            :inventaire, :choices, :ruleset_id, :ruleset_version, :schema_version,
            :xp, :image_url, :extra, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            discord_user_id = excluded.discord_user_id,
            guild_id = excluded.guild_id,
            nom = excluded.nom,
            race_id = excluded.race_id,
            classe = excluded.classe,
            niveau = excluded.niveau,
            force = excluded.force,
            dex = excluded.dex,
            con = excluded.con,
            int_score = excluded.int_score,
            sag = excluded.sag,
            cha = excluded.cha,
            pv_actuels = excluded.pv_actuels,
            pv_max = excluded.pv_max,
            emplacements_sorts = excluded.emplacements_sorts,
            specialisation = excluded.specialisation,
            inventaire = excluded.inventaire,
            choices = excluded.choices,
            ruleset_id = excluded.ruleset_id,
            ruleset_version = excluded.ruleset_version,
            schema_version = excluded.schema_version,
            xp = excluded.xp,
            image_url = excluded.image_url,
            extra = excluded.extra,
            updated_at = excluded.updated_at
        """,
        row,
    )


def migrate_json_v2_to_sqlite(
    conn: sqlite3.Connection,
    *,
    json_path: Path | None = None,
    default_guild_id: str = "0",
) -> int:
    """Importe data/characters/v2/characters.json → SQLite (upsert)."""
    path = json_path or get_v2_characters_path()
    if not path.is_file():
        return 0
    raw = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for char_data in raw.get("characters", {}).values():
        if "guild_id" not in char_data:
            char_data["guild_id"] = default_guild_id
        character = Character.from_dict(char_data)
        upsert_character(conn, character)
        count += 1
    if count:
        logger.info("Migration JSON v2 -> SQLite : %d personnage(s)", count)
    return count


def list_characters_by_guild(conn: sqlite3.Connection, guild_id: str) -> list[Character]:
    """Liste tous les personnages d'un serveur Discord."""
    rows = conn.execute(
        "SELECT * FROM personnages WHERE guild_id = ? ORDER BY nom COLLATE NOCASE",
        (str(guild_id),),
    ).fetchall()
    return [row_to_character(row) for row in rows]


def get_active_character_id(
    conn: sqlite3.Connection,
    owner_id: str,
    guild_id: str,
) -> str | None:
    row = conn.execute(
        """
        SELECT character_id FROM perso_actif
        WHERE discord_user_id = ? AND guild_id = ?
        """,
        (str(owner_id), str(guild_id)),
    ).fetchone()
    return str(row["character_id"]) if row else None


def set_active_character_id(
    conn: sqlite3.Connection,
    owner_id: str,
    guild_id: str,
    character_id: str,
) -> None:
    conn.execute(
        """
        INSERT INTO perso_actif (discord_user_id, guild_id, character_id, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(discord_user_id, guild_id) DO UPDATE SET
            character_id = excluded.character_id,
            updated_at = excluded.updated_at
        """,
        (str(owner_id), str(guild_id), character_id, _utc_now()),
    )


def clear_active_for_character(conn: sqlite3.Connection, character_id: str) -> None:
    conn.execute(
        "DELETE FROM perso_actif WHERE character_id = ?",
        (character_id,),
    )


def clear_active_character(
    conn: sqlite3.Connection,
    owner_id: str,
    guild_id: str,
) -> None:
    conn.execute(
        """
        DELETE FROM perso_actif
        WHERE discord_user_id = ? AND guild_id = ?
        """,
        (str(owner_id), str(guild_id)),
    )


def migrate_fixtures_to_sqlite(
    conn: sqlite3.Connection,
    *,
    default_guild_id: str = "0",
) -> int:
    """Importe les fixtures repo (Joe, Marie) si absentes de la base."""
    fixtures_dir = get_project_root() / "fixtures" / "characters"
    if not fixtures_dir.is_dir():
        return 0
    count = 0
    for fixture_path in sorted(fixtures_dir.glob("*.v2.json")):
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        for char_data in raw.get("characters", {}).values():
            owner = str(char_data.get("owner_id", ""))
            if owner.startswith("REPLACE_"):
                continue
            if "guild_id" not in char_data:
                char_data["guild_id"] = default_guild_id
            char_id = char_data["id"]
            existing = conn.execute(
                "SELECT 1 FROM personnages WHERE id = ?", (char_id,)
            ).fetchone()
            if existing:
                continue
            upsert_character(conn, Character.from_dict(char_data))
            count += 1
            logger.info("Fixture importée : %s (%s)", char_data.get("name"), char_id)
    return count


def run_startup_migrations(
    db_path: Path | None = None,
    *,
    default_guild_id: str = "0",
    json_path: Path | None = None,
    include_fixtures: bool = False,
) -> Path:
    """
    Init DB + import one-shot JSON v2 (si jamais fait).

    SQLite est la source de vérité : les imports ne s'exécutent qu'une fois.
    Les fixtures ne sont jamais injectées en production (include_fixtures=False).
    """
    path = init_database(db_path)
    with get_connection(path) as conn:
        json_count = 0
        fixture_count = 0

        if not is_one_shot_import_done(conn, META_JSON_V2_IMPORT_DONE):
            existing = conn.execute("SELECT COUNT(*) FROM personnages").fetchone()[0]
            if existing == 0:
                json_count = migrate_json_v2_to_sqlite(
                    conn,
                    json_path=json_path,
                    default_guild_id=default_guild_id,
                )
            else:
                logger.info(
                    "Base déjà peuplée — import JSON v2 ignoré (bootstrap one-shot)"
                )
            mark_one_shot_import_done(conn, META_JSON_V2_IMPORT_DONE)
        else:
            logger.debug("Import JSON v2 déjà effectué — ignoré")

        if include_fixtures and not is_one_shot_import_done(conn, META_FIXTURES_IMPORT_DONE):
            existing = conn.execute("SELECT COUNT(*) FROM personnages").fetchone()[0]
            if existing == 0:
                fixture_count = migrate_fixtures_to_sqlite(
                    conn, default_guild_id=default_guild_id
                )
            mark_one_shot_import_done(conn, META_FIXTURES_IMPORT_DONE)

        total = conn.execute("SELECT COUNT(*) FROM personnages").fetchone()[0]
        logger.info(
            "Personnages en base : %d (json=%d, fixtures=%d)",
            total,
            json_count,
            fixture_count,
        )
    return path
