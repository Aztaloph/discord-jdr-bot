# interfaces/api/app.py
"""
API HTTP — interface de jeu v1 (fiche, sorts, repos ; combat en extension).

Routes contractuelles sous ``/v1/`` — voir ``docs/api/CONTRAT.md``.

Diagnostic dev (hors contrat v1) : ``/debug/events``, ``GET /``, ``/static/*``.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from interfaces.api.combat_routes import register_combat_routes
from interfaces.api.diagnostic.event_buffer import EventRingBuffer
from interfaces.api.diagnostic.recording_bus import RecordingEventBus
from interfaces.api.errors import ApiError, register_error_handlers
from interfaces.api.sheet_view import build_character_sheet_response
from jdr_engine.application.combat_service import CombatService
from jdr_engine.core.events.bus import EventBus

from jdr_engine.application.dto.output_serializers import (
    long_rest_result_to_dict,
    short_rest_result_to_dict,
    spell_cast_result_to_dict,
)
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.combat_log_repository import SqliteCombatLogRepository
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.rest import RestError, apply_long_rest, apply_short_rest
from jdr_engine.rules.spellcasting.cast import SpellCastError, cast_spell

STATIC_DIR = Path(__file__).resolve().parent / "static"


class CastSpellRequest(BaseModel):
    spell_id: str = Field(min_length=1)


class ShortRestRequest(BaseModel):
    dice_to_spend: int = Field(ge=0)


def create_app(
    *,
    engine: RuleEngine | None = None,
    db_path: Path | None = None,
    locale: str = "fr",
    event_bus: EventBus | None = None,
    event_buffer: EventRingBuffer | None = None,
    combat_initiative_rng=None,
    combat_attack_rng=None,
) -> FastAPI:
    """
    Fabrique de l'application FastAPI.

    ``engine`` et ``db_path`` sont injectables pour les tests ; par défaut,
    charge le ruleset ``dnd5e`` et utilise la base SQLite du bot (``data/bot.db``).
    """
    if engine is None:
        engine = RuleEngine.load("dnd5e", validate=True, strict=True)
    resolved_db_path = init_database(db_path)
    repository = SqliteCharacterRepository(resolved_db_path)
    combat_repository = SqliteCombatRepository(resolved_db_path)

    if event_bus is None:
        inner = EventBus()
        buffer = event_buffer if event_buffer is not None else EventRingBuffer()
        event_bus = RecordingEventBus(inner, buffer)
    elif event_buffer is not None:
        raise ValueError("event_buffer sans RecordingEventBus est incohérent")

    combat_service = CombatService(
        event_bus,
        combat_repository,
        repository,
        SqliteCombatLogRepository(resolved_db_path),
        engine,
        register_auto_save_handler=False,
    )

    app = FastAPI(
        title="JDR Engine API",
        description="JDR Engine — API de jeu v1 (fiche, sorts, repos, combat).",
        version="1.0.0",
    )
    register_error_handlers(app)
    app.state.event_bus = event_bus

    def _load_character(character_id: str) -> Character:
        character = repository.get_by_id(character_id)
        if character is None:
            raise ApiError(
                404,
                "CHARACTER_NOT_FOUND",
                "Personnage introuvable.",
            )
        return character

    @app.get("/v1/characters/{character_id}/sheet")
    def get_sheet(character_id: str) -> dict:
        character = _load_character(character_id)
        return build_character_sheet_response(
            character,
            engine,
            combat_repository,
            locale=locale,
        )

    @app.post("/v1/characters/{character_id}/cast")
    def cast(character_id: str, body: CastSpellRequest) -> dict:
        character = _load_character(character_id)
        try:
            result = cast_spell(
                character,
                body.spell_id,
                engine,
                locale=locale,
                persist_slots=True,
            )
        except SpellCastError as exc:
            raise ApiError(
                409,
                "SPELL_CAST_REJECTED",
                str(exc),
            ) from exc
        repository.save(result.updated_character or character)
        return spell_cast_result_to_dict(result)

    @app.post("/v1/characters/{character_id}/short-rest")
    def short_rest(character_id: str, body: ShortRestRequest) -> dict:
        character = _load_character(character_id)
        try:
            updated, result = apply_short_rest(
                character, engine, body.dice_to_spend
            )
        except RestError as exc:
            raise ApiError(
                409,
                "REST_REJECTED",
                str(exc),
            ) from exc
        repository.save(updated)
        return short_rest_result_to_dict(result)

    @app.post("/v1/characters/{character_id}/long-rest")
    def long_rest(character_id: str) -> dict:
        character = _load_character(character_id)
        try:
            updated, result = apply_long_rest(character, engine)
        except RestError as exc:
            raise ApiError(
                409,
                "REST_REJECTED",
                str(exc),
            ) from exc
        repository.save(updated)
        return long_rest_result_to_dict(result)

    register_combat_routes(
        app,
        combat_service=combat_service,
        character_repository=repository,
        combat_repository=combat_repository,
        engine=engine,
        locale=locale,
        initiative_rng=combat_initiative_rng,
        attack_rng=combat_attack_rng,
    )

    @app.get("/")
    def serve_client() -> FileResponse:
        """Page d'accueil — client web statique (HTML/CSS/JS vanilla)."""
        index = STATIC_DIR / "index.html"
        if not index.is_file():
            raise ApiError(
                500,
                "INTERNAL_ERROR",
                "Client web introuvable (interfaces/api/static/index.html).",
            )
        return FileResponse(index)

    @app.get("/debug/events")
    def list_debug_events() -> JSONResponse:
        """Événements publiés depuis le démarrage (tampon mémoire, plus récent en premier)."""
        bus = app.state.event_bus
        if isinstance(bus, RecordingEventBus):
            entries = bus.buffer.list_newest_first()
        else:
            entries = []
        return JSONResponse(entries)

    @app.get("/debug/events/view")
    def debug_events_page() -> FileResponse:
        """Page HTML de diagnostic — flux d'événements (rafraîchissement périodique)."""
        page = STATIC_DIR / "events.html"
        if not page.is_file():
            raise ApiError(
                500,
                "INTERNAL_ERROR",
                "Page diagnostic introuvable (interfaces/api/static/events.html).",
            )
        return FileResponse(page)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app
