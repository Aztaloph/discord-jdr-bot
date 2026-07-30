# API HTTP locale — banc de test hors Discord

Petite API FastAPI (`interfaces/api/`) pour observer un personnage évoluer sans
passer par Discord : consulter sa fiche, lancer un sort, prendre un repos.

## Installation

Les dépendances API sont isolées du moteur (`jdr_engine/` reste importable sans
elles). Deux options équivalentes :

```bash
# via requirements.txt (environnement complet bot + API, comme la CI)
venv\Scripts\python.exe -m pip install -r requirements.txt

# ou dépendances API seules
venv\Scripts\python.exe -m pip install fastapi uvicorn
```

## Lancement

L'application s'obtient par la fabrique `create_app` (pas d'instance au niveau
module, pour éviter de charger le moteur à l'import) :

```bash
venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
```

L'API écoute sur `http://127.0.0.1:8000`. Documentation interactive générée :
`http://127.0.0.1:8000/docs`.

Par défaut, elle charge le ruleset `dnd5e` et utilise la base SQLite du bot
(`data/bot.db`) — les personnages créés via Discord y sont donc visibles,
identifiés par leur id court (celui affiché par `/perso-afficher`).

## Endpoints

| Méthode | Route | Corps | Effet |
|---|---|---|---|
| GET | `/characters/{id}/sheet` | — | Fiche calculée (lecture seule) |
| POST | `/characters/{id}/cast` | `{"spell_id": "hex"}` | Lance un sort, persiste l'état |
| POST | `/characters/{id}/short-rest` | `{"dice_to_spend": 2}` | Repos court, persiste l'état |
| POST | `/characters/{id}/long-rest` | — | Repos long, persiste l'état |

Exemple :

```bash
curl http://127.0.0.1:8000/characters/abc123/sheet
curl -X POST http://127.0.0.1:8000/characters/abc123/cast -H "Content-Type: application/json" -d "{\"spell_id\": \"hex\"}"
```

## Codes d'erreur

| Code | Sens |
|---|---|
| 404 | Personnage introuvable |
| 409 | Règle métier violée (`SpellCastError`, `RestError`) — message dans `detail` |
| 422 | Corps de requête invalide (validation pydantic) |
| 500 | Erreur inattendue (distincte du métier) |

## Limites connues (assumées dans ce lot)

- **Pas de contrôle de concurrence** : le dernier écrivain gagne, comme pour le
  bot Discord. Ne pas utiliser l'API et le bot simultanément sur le même
  personnage si l'ordre des écritures compte.
- Pas d'authentification : usage local uniquement.
- Pas d'endpoint de création ni de montée de niveau dans ce lot.
- Les DTO n'exposent que des **données structurées** — aucun texte pré-formaté
  d'affichage (voir `jdr_engine/application/dto/output_serializers.py`).
