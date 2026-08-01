# interfaces/api/app.py
"""
API HTTP de lecture et d'action — banc de test pour observer un personnage
évoluer hors Discord.

Endpoints :
- ``GET  /characters/{character_id}/sheet``      — fiche calculée (DTO).
- ``POST /characters/{character_id}/cast``       — lancer un sort.
- ``POST /characters/{character_id}/short-rest`` — repos court.
- ``POST /characters/{character_id}/long-rest``  — repos long.

Règles de fonctionnement :
- Toute action **persiste systématiquement** le personnage mis à jour, dans la
  même fonction qui l'exécute — aucune persistance n'est laissée au client.
- ``cast_spell`` est appelé avec ``persist_slots=True`` : ``updated_character``
  est alors renseigné et c'est **cet objet** qui est persisté, garantissant que
  l'état en base correspond à l'état retourné dans la réponse. (Avec
  ``persist_slots=False``, ``cast_spell`` mute le personnage reçu en place et
  laisse ``updated_character`` à ``None`` — piège documenté, ne pas l'utiliser ici.)
- Erreurs métier (``SpellCastError``, ``RestError``) → **409** avec message.
- Personnage introuvable → **404** dédié.
- Corps de requête invalide → **422** (validation FastAPI/pydantic).
- Toute autre exception → **500** (erreur inattendue, distincte du métier).

**Pas de contrôle de concurrence dans ce lot** : comme pour le bot Discord,
le dernier écrivain gagne (``save`` fait un upsert complet, sans verrou ni
version). Deux écritures concurrentes sur le même personnage se recouvrent.

Lancement local : voir ``docs/API_LOCAL.md`` (fabrique ``create_app`` + uvicorn).
Client web statique : ``GET /`` (HTML) · assets ``/static/*`` (même origine, pas de CORS).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jdr_engine.application.dto.output_serializers import (
    character_sheet_to_dict,
    long_rest_result_to_dict,
    short_rest_result_to_dict,
    spell_cast_result_to_dict,
)
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.calculator import build_character_sheet
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

    app = FastAPI(
        title="JDR Engine API",
        description="JDR Engine — banc de test HTTP (fiche, sorts, repos).",
        version="0.1.0",
    )

    def _load_character(character_id: str) -> Character:
        character = repository.get_by_id(character_id)
        if character is None:
            raise HTTPException(
                status_code=404, detail="Personnage introuvable."
            )
        return character

    @app.get("/characters/{character_id}/sheet")
    def get_sheet(character_id: str) -> dict:
        character = _load_character(character_id)
        sheet = build_character_sheet(character, engine, locale=locale)
        return character_sheet_to_dict(sheet)

    @app.post("/characters/{character_id}/cast")
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
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        # persist_slots=True garantit updated_character non nul ; le repli sur
        # `character` (muté en place par cast_spell) couvre tout cas contraire.
        repository.save(result.updated_character or character)
        return spell_cast_result_to_dict(result)

    @app.post("/characters/{character_id}/short-rest")
    def short_rest(character_id: str, body: ShortRestRequest) -> dict:
        character = _load_character(character_id)
        try:
            updated, result = apply_short_rest(
                character, engine, body.dice_to_spend
            )
        except RestError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        repository.save(updated)
        return short_rest_result_to_dict(result)

    @app.post("/characters/{character_id}/long-rest")
    def long_rest(character_id: str) -> dict:
        character = _load_character(character_id)
        try:
            updated, result = apply_long_rest(character, engine)
        except RestError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        repository.save(updated)
        return long_rest_result_to_dict(result)

    @app.get("/")
    def serve_client() -> FileResponse:
        """Page d'accueil — client web statique (HTML/CSS/JS vanilla)."""
        index = STATIC_DIR / "index.html"
        if not index.is_file():
            raise HTTPException(
                status_code=500,
                detail="Client web introuvable (interfaces/api/static/index.html).",
            )
        return FileResponse(index)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app
