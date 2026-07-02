# Migration progressive — Bot Discord → Moteur JDR

Voir [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) pour la vision complète.

## Statut

| Phase | Statut | Description |
|---|---|---|
| **0** | ✅ Terminée | Ossature + dice → jdr_engine |
| **1** | ✅ Terminée | Compendium dnd5e + Rule Engine MVP |
| **2** | ✅ Terminée | Domain + Persistence v2 + CharacterService |
| **3** | ✅ Terminée | Discord branché sur moteur v2 (feature flag) |
| **4** | ✅ Terminée | Affichage enrichi (lore + portraits Compendium) |
| **4.5** | ✅ Terminée | Hook d20 + traits actifs (Halfelin, Rôdeur niv.1) |
| **4.6** | ✅ Terminée | `/roll` Discord branché sur hook d20 + traits |
| 5 | ⬜ | Backgrounds, skills |

## Phase 0 — Fondations (2026-07-02)

### Livrables

- [x] Package `jdr_engine/` avec sous-modules vides (domain, rules, game, …)
- [x] `jdr_engine/dice/` — parser, roller, models (ex `bot/utils/dice_parser.py`)
- [x] Re-export legacy `bot/utils/dice_parser.py` (compatibilité cogs)
- [x] `pyproject.toml` + `pydantic` dans requirements
- [x] Dossiers `compendium/`, `interfaces/`, `tools/`, `plugins/`, `tests/`
- [x] Tests déplacés vers `tests/unit/test_dice.py`

### Validation

```powershell
cd C:\Users\aztal\Desktop\discord-jdr-bot
venv\Scripts\activate
pip install -r requirements.txt
python -m unittest tests.unit.test_dice -v
python -c "import main; from jdr_engine.dice import roll; print('OK')"
python main.py   # bot Discord inchangé
```

### Ce qui n'a PAS changé

- `bot/cogs/character.py` — intact
- `bot/cogs/dice.py` — import legacy `bot.utils.dice_parser`
- `main.py` — intact
- Persistance personnages — intacte

---

## Phase 1 — Compendium & Rule Engine MVP (2026-07-02)

### Livrables

- [x] `compendium/dnd5e/` — manifest, config, 12 entrées (4 races, 4 classes, 4 traits)
- [x] Lore FR/EN pour elf ; lore FR pour human, dwarf, halfling
- [x] `jdr_engine/compendium/` — loader, registry, validator, presenter, schemas
- [x] `jdr_engine/rules/` — RuleEngine, resolver, RulesetContext
- [x] `tools/validate_compendium.py`
- [x] 23 nouveaux tests (60 au total)

### Validation

```powershell
pip install -r requirements.txt
python -m unittest discover -s tests -v
python tools/validate_compendium.py dnd5e
python main.py
```

### Exemple

```python
from jdr_engine.rules import RuleEngine

engine = RuleEngine.load("dnd5e")
engine.list_entities("race")              # 4 races
engine.get_ability_bonuses("elf")         # {"dex": 2}
engine.get_race_traits("elf")             # 4 traits résolus
engine.presenter.get_lore("race", "elf", locale="fr")
```

### Ce qui n'a PAS changé

- Discord — pas encore branché sur Rule Engine (Phase 3)
- Persistance personnages v1 — intacte

---

## Phase 2 — Domain & Persistence v2 (2026-07-02)

### Livrables

- [x] `jdr_engine/domain/character/` — Character, CharacterSheet, AbilityScores
- [x] `jdr_engine/rules/calculator.py` — stats dérivées (PV, CA, modificateurs)
- [x] `jdr_engine/persistence/` — JsonCharacterRepository (v2)
- [x] `jdr_engine/application/character_service.py` — create, get_sheet, list, delete
- [x] `jdr_engine/persistence/migrations/v1_to_v2.py`
- [x] `tools/migrate_persistence.py`
- [x] 13 nouveaux tests (73 au total)

### Persistance v2

Fichier séparé : `data/characters/v2/characters.json`

Le v1 (`data/characters/characters.json`) reste utilisé par le bot Discord actuel.

### Migration v1 → v2

```powershell
python tools/migrate_persistence.py --backup-v1
```

### Exemple CharacterService

```python
from jdr_engine.application import CharacterService, CreateCharacterCommand, GetCharacterSheetQuery
from jdr_engine.persistence.character_repository import JsonCharacterRepository
from jdr_engine.rules import RuleEngine

engine = RuleEngine.load("dnd5e")
repo = JsonCharacterRepository()
service = CharacterService(repo, engine)

char = service.create(CreateCharacterCommand(
    owner_id="372519173097652236",
    name="Aldric",
    race_id="elf",
    class_id="fighter",
))
sheet = service.get_sheet(GetCharacterSheetQuery(character_id=char.id, owner_id=char.owner_id))
print(sheet.hp_max, sheet.ability_scores["dex"])  # 10, 12
```

### Ce qui n'a PAS changé

- Bot Discord — utilise encore `bot/models/character.py` v1 (Phase 3)

---

## Phase 3 — Discord → moteur v2 (2026-07-02)

### Livrables

- [x] `interfaces/discord/` — settings, startup, container, handlers, views, formatters
- [x] Wizard création v2 : Select race/classe depuis Compendium + modal nom
- [x] Commandes routées : `/perso-creer`, `/perso-liste`, `/perso-afficher`, `/perso-mp`, `/perso-supprimer`
- [x] Autocomplete noms personnages (v2)
- [x] Feature flag `USE_ENGINE_V2` (défaut `true`) + fallback legacy si échec init
- [x] `main.py` — `bot.jdr = init_discord_jdr(config)` au démarrage

### Activation

`.env` ou `config.json` :

```env
USE_ENGINE_V2=true
DEFAULT_RULESET=dnd5e
DEFAULT_LOCALE=fr
```

Pour revenir au mode legacy (modals v1, `data/characters/characters.json`) :

```env
USE_ENGINE_V2=false
```

### Validation

```powershell
venv\Scripts\activate
python -m unittest discover -s tests -v
python main.py
```

Dans Discord :

1. `/perso-liste` — doit lister les personnages v2 (`data/characters/v2/characters.json`)
2. `/perso-creer` — menus Select race/classe + modal nom
3. `/perso-afficher` — fiche calculée par le moteur (traits, PV, CA)

### Non disponible en v2 (phases ultérieures)

- `/perso-modifier`, `/perso-modifier-identite`, `/perso-attaque-ajouter` → message informatif

### Ce qui n'a PAS changé

- Mode legacy intact si `USE_ENGINE_V2=false`
- `bot/cogs/dice.py` — inchangé
- Compendium — ajouter une race dans `compendium/dnd5e/entries/races/` la rend disponible dans le Select sans code Python

---

## Phase 4 — Affichage enrichi (2026-07-02)

### Livrables

- [x] `jdr_engine/core/assets/resolver.py` — `AssetResolver` (portraits locaux)
- [x] `interfaces/discord/formatters/lore_text.py` — troncature lore pour Discord
- [x] `build_character_display()` — lore race/classe dans la description embed
- [x] Portraits Compendium via `entries/.../assets/portrait.png` (pièce jointe Discord)
- [x] Lore rôdeur (`rogue/lore.fr.md`) + extrait lore à la création
- [x] Traits raciaux **et** section attaques affichés ensemble

### Affichage `/perso-afficher`

La description de l'embed contient le lore Compendium :

```
Halfelin — Les halfelins sont un peuple affable…

Rôdeur — Le rôdeur traque ses proies…
```

### Portraits (optionnel)

Placez un fichier dans le Compendium :

```
compendium/dnd5e/entries/races/halfling/assets/portrait.png
```

Relancez le bot — `/perso-afficher` affichera le portrait en miniature.

Priorité : portrait race → portrait classe → `image_url` du personnage.

### Validation

```powershell
python -m unittest discover -s tests -v
python main.py
```

Dans Discord : `/perso-afficher Doudou` → lore Halfelin + Rôdeur en haut de la fiche.

---

## Bloc B — Données SRD & garde-fous (2026-07-02) ✅

Correction des stats via SRD 5.1 (`5e-database` src/2014) + outillage non destructif.

### Livrables

- [x] Fix mapping `rogue` → Roublard, nouvelle classe `ranger` (Rôdeur, d10)
- [x] Fix `halfling` size → `small`
- [x] `tools/import_srd_mechanics.py` — import mécanique idempotent, préserve `name.fr`, traits, `languages.choose`, TODO Phase 4.5
- [x] Tests : Halfelin+Rôdeur (DEX 12, PV 10), Roublard (PV 8)
- [x] JSON Schema : `compendium/schemas/race-mechanics.schema.json`, `class-mechanics.schema.json`
- [x] Validation L4 : `schema_strict=True` en CI (`.github/workflows/ci.yml`)
- [x] Import réel : 5 classes enrichies, 4 races inchangées, 0 `name.fr` modifié

### Validation CI (local)

```powershell
python -m unittest discover -s tests -v          # 93+ tests
python tools/validate_compendium.py dnd5e        # strict, 0 erreur
```

### Modes validation Compendium

| Contexte | Commande / config | Schema strict |
|---|---|---|
| CI | `validate_compendium.py dnd5e` | erreurs |
| Dev bot | `COMPENDIUM_STRICT=false` ou `--warn` | warnings |
| Bot prod | `COMPENDIUM_STRICT=true` (défaut) | erreurs |

---

## Phase 4.5 — Traits actifs & hook d20 (2026-07-03) ✅

Effets mécaniques SRD 5.1 2014 sur les jets de d20 via un hook central.

### Livrables

- [x] `jdr_engine/dice/d20.py` — `roll_d20()` : point d'entrée unique (attaque, test, sauvegarde)
- [x] Hooks **avant** jet (avantage, maîtrise x2) et **après** jet (relance nat. 1)
- [x] `jdr_engine/rules/roll_effects.py` — collecte effets Compendium + `roll_d20_for_character()`
- [x] Traits Halfelin : **Brave**, **Chanceux** (`traits/brave`, `traits/lucky`)
- [x] Features Rôdeur niv.1 : **Ennemi juré**, **Explorateur-né**
- [x] 24 nouveaux tests (118 au total)

### API hook d20 (résumé)

| Entrée | Description |
|---|---|
| `D20RollRequest.roll_type` | `attack` \| `ability_check` \| `saving_throw` |
| `D20RollRequest.base_mode` | avantage / désavantage externe |
| `D20RollRequest.save_versus_condition` | ex. `frightened` (Brave) |
| `D20RollRequest.tracking` | pistage Ennemi juré (Survival) |
| `D20RollRequest.recalling_favored_enemy_info` | rappel Intelligence Ennemi juré |
| `D20RollRequest.favored_terrain_related` | jet lié au terrain favori |
| `D20RollContext.effects` | effets Compendium actifs |

| Sortie | Description |
|---|---|
| `D20RollResult.kept_value` | d20 retenu (après adv/dis + relance) |
| `D20RollResult.applied_effects` | piste d'audit |
| `D20RollResult.rerolled` | relance Chanceux déclenchée |

Doc complète : docstring module `jdr_engine/dice/d20.py`.

### Validation

```powershell
python -m unittest discover -s tests -v          # 118 tests
python tools/validate_compendium.py dnd5e
```

### Ignoré (données SRD non implémentées)

| Entité | Effet SRD | Raison |
|---|---|---|
| Halfelin | Halfling Nimbleness | déplacement, pas de jet d20 |
| Halfelin | Naturally Stealthy | camouflage, pas de jet d20 |
| Rôdeur | Ennemi juré — langue | choix joueur, hors hook d20 |
| Rôdeur | Explorateur-né — voyage | règles exploration, hors jet d20 |
| Rôdeur | Style de combat, sorts | hors périmètre Phase 4.5 |

---

## Phase 4.6 — `/roll` Discord + traits (2026-07-03) ✅

Branchement de la commande slash `/roll` sur le hook d20 du moteur v2.

### Livrables

- [x] `interfaces/discord/handlers/dice.py` — `execute_roll()` + résolution personnage
- [x] `bot/cogs/dice.py` — paramètre optionnel `perso` (autocomplete)
- [x] d20 + personnage → traits actifs (Chanceux, Brave, etc.)
- [x] Embed enrichi : titre perso, champ 🍀 Chanceux, traits appliqués
- [x] 8 tests (`test_discord_dice_handler.py`)

### Comportement `/roll`

| Situation | Comportement |
|---|---|
| `d20` / `1d20+5` + 1 seul perso | traits auto (sans paramètre) |
| `d20` + paramètre `perso:Doudou` | traits du perso nommé |
| Plusieurs persos sans `perso` | jet classique + hint footer |
| `3d6`, `2d20`, etc. | jet classique (pas de hook traits) |

### Test Discord (Chanceux)

```powershell
.\venv\Scripts\activate
python main.py
```

Dans Discord :

```
/roll dé:d20 perso:Doudou
```

Répéter jusqu'à un **1 naturel** → embed doré avec champ **🍀 Chanceux** et deux d20 affichés (1 barré + relance).

### Validation

```powershell
python -m unittest discover -s tests -v   # 126 tests
python main.py
```
