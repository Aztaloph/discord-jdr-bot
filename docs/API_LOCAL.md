# docs/API_LOCAL.md
# API HTTP locale — banc de test (interface de jeu v1)

Petite API FastAPI (`interfaces/api/`) — **seule interface de jeu** du projet.
Contrat : `docs/api/CONTRAT.md`.

## Installation

```bash
venv\Scripts\python.exe -m pip install -r requirements.txt
# ou : pip install fastapi uvicorn
```

## Lancement

```bash
venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
```

Écoute : `http://127.0.0.1:8000` · Swagger : `http://127.0.0.1:8000/docs`

## Endpoints v1

| Méthode | Route | Corps | Effet |
|---|---|---|---|
| GET | `/v1/characters/{id}/sheet` | — | Fiche calculée (DTO) |
| POST | `/v1/characters/{id}/cast` | `{"spell_id": "hex"}` | Lance un sort |
| POST | `/v1/characters/{id}/short-rest` | `{"dice_to_spend": 2}` | Repos court |
| POST | `/v1/characters/{id}/long-rest` | — | Repos long |

Exemple :

```bash
curl http://127.0.0.1:8000/v1/characters/abc123/sheet
curl -X POST http://127.0.0.1:8000/v1/characters/abc123/cast -H "Content-Type: application/json" -d "{\"spell_id\": \"hex\"}"
```

## Format d'erreur

Toutes les erreurs 4xx/5xx métier renvoient :

```json
{
  "error": {
    "code": "CHARACTER_NOT_FOUND",
    "message": "Personnage introuvable.",
    "details": {}
  }
}
```

| HTTP | Exemples `code` |
|---|---|
| 404 | `CHARACTER_NOT_FOUND` |
| 409 | `SPELL_CAST_REJECTED`, `REST_REJECTED` |
| 422 | `VALIDATION_ERROR` |
| 500 | `INTERNAL_ERROR` |

## Limites connues

- Pas de contrôle de concurrence (last-writer-wins).
- Pas d'authentification — usage local.
- Endpoints combat : lot 1 en cours (`/v1/combats/…`).
