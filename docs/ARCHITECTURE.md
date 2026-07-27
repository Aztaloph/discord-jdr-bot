# Architecture — état actuel du dépôt

> Ce document décrit l'architecture **réellement implémentée**, vérifiée contre le code source. En cas d'écart avec un autre document, **le code prime**.
>
> Architecture cible (non implémentée ou partielle) : [`ARCHITECTURE_TARGET.md`](ARCHITECTURE_TARGET.md). Stratégie produit : [`VISION.md`](../VISION.md). Plan opérationnel : [`ROADMAP.md`](../ROADMAP.md). Règles agents : [`AGENTS.md`](../AGENTS.md).

| Attribut | Valeur |
|---|---|
| **Date** | 2026-07-27 |
| **Ruleset** | `dnd5e@1.0.0` — 166 entrées Compendium |
| **Moteur** | `jdr-engine@0.1.0` (`pyproject.toml`) |
| **Tests** | 647 (`unittest`) |
| **ADRs** | ADR-001, ADR-002, ADR-003 |

---

## 1. Vue d'ensemble

```
main.py
  ├── bot.cogs.*              → interfaces/discord/*  →  jdr_engine/*
  └── init_discord_jdr()      →  RuleEngine + SqliteCharacterRepository + CharacterService
```

**Invariant vérifié** : `jdr_engine/` n'importe ni `discord`, ni `interfaces`, ni `bot` (0 occurrence).

Sens des dépendances : `bot/` → `interfaces/discord/` → `jdr_engine/application` → `rules` / `domain` / `persistence`.

---

## 2. Packages `jdr_engine/` — réels vs placeholders

| Package | État | Contenu notable |
|---|---|---|
| `domain/character/` | **Réel** | `Character`, `CharacterSheet`, `AbilityScores`, `choices_schema` |
| `compendium/` | **Réel** | `loader`, `registry`, `validator`, `presenter`, `mechanics_schema` |
| `rules/` | **Réel** | `engine`, `calculator`, `character_creation/`, `character_progression/`, `class_features/`, `racial/`, `rest/`, `spellcasting/` |
| `application/` | **Réel** | `CharacterService` (+ DTOs) — seul service applicatif |
| `persistence/` | **Réel** | SQLite (`database.py`, `sqlite_character_repository.py`), JSON legacy, `migrations/v1_to_v2.py` |
| `dice/` | **Réel** | `parser`, `roller`, `d20`, `models` |
| `core/assets/` | **Réel** | `AssetResolver`, `AssetReference` |
| `core/events/` | Placeholder | `__init__.py` 1 ligne — jamais importé |
| `core/i18n/` | Placeholder | idem |
| `core/config/` | Placeholder | idem |
| `core/plugins/` | Placeholder | idem |
| `game/` | Placeholder | idem |

---

## 3. Compendium (données)

```
compendium/
├── schemas/
│   ├── race-mechanics.schema.json
│   └── class-mechanics.schema.json
├── _schemas/          # vide (.gitkeep)
└── dnd5e/
    ├── manifest.yaml  # version 1.0.0, entry_types: races, classes, traits, spells
    ├── config.yaml    # abilities[], level_table
    └── entries/
        ├── races/     (9)
        ├── classes/   (12)
        ├── traits/    (103)
        └── spells/    (42) — schema_version 2.0
```

**Total** : 166 fichiers `definition.yaml`.

Chargement : `load_ruleset()` → `CompendiumRegistry(manifest, config, entries)` → `RuleEngine.load(ruleset_id)`.

Séparation moteur / UI (ADR-002) :

- `RuleEngine.get_entity()` lit `definition.yaml` uniquement.
- `CompendiumPresenter.get_lore()` lit `lore.{locale}.md`.
- `AssetResolver.resolve_path()` / `resolve_portrait()` retournent un `Path` local (ou `None`).

---

## 4. Validation Compendium

Niveaux implémentés dans `jdr_engine/compendium/validator.py` :

| Niveau | Comportement |
|---|---|
| L1 — Schéma | Pydantic au chargement |
| L2 — Références | Refs `traits/*` cassées → erreur |
| L3 — Cohérence | id / type au chargement |
| L4 — JSON Schema `mechanics` | Races et classes vs `compendium/schemas/*.schema.json` |
| L5 — Lore (warn) | `lore.{locale}.md` manquant (races) |

Pas de niveau L6. Vérification additionnelle : caractéristique inconnue dans `ability_score_increase`.

**CLI** (`tools/validate_compendium.py`) :

```bash
python tools/validate_compendium.py              # dnd5e, strict (défaut)
python tools/validate_compendium.py dnd5e --warn # n'échoue pas sur les erreurs
```

**Boot Discord** : `DiscordSettings.compendium_strict` → `RuleEngine.load(..., strict=...)`.

---

## 5. Persistance

Backend de production : **SQLite** (`data/bot.db`).

```
jdr_engine/persistence/
├── database.py                    # schéma, DB_SCHEMA_VERSION=1, run_startup_migrations()
├── sqlite_character_repository.py # repository runtime
├── character_repository.py        # Protocol + JsonCharacterRepository (tests / legacy)
├── protocols.py
└── migrations/
    └── v1_to_v2.py                # migrate_v1_to_v2(), convert_v1_record(), backup_v1()
```

**Tables** : `personnages` (dont `ruleset_id`, `ruleset_version`, `schema_version`), `schema_meta`, `perso_actif`.

**Chemins JSON legacy** :

- v1 : `data/characters/characters.json`
- v2 : `data/characters/v2/characters.json`
- Fixtures : `fixtures/characters/*.v2.json`

**Mapping classes v1 → Compendium** (`v1_to_v2.py`) : `Guerrier`→`fighter`, `Magicien`→`wizard`, `Rôdeur`→`ranger`, `Roublard`→`rogue`, `Clerc`→`cleric`.

**Boot** (`interfaces/discord/startup.py`) : `run_startup_migrations()` → `SqliteCharacterRepository(db_path)` → `CharacterService(repo, engine)`.

---

## 6. Application layer

**`CharacterService`** (`jdr_engine/application/character_service.py`) — seul service :

- CRUD personnages, fiches, actif par guild
- Wizard création (`create_from_wizard`)
- Repos (`long_rest_on_guild`, `short_rest_on_guild`)
- Préparation sorts, montée de niveau
- Outils MJ grimoire

Pas de `CompendiumService`, `CombatService`, `EventBus`, `MigrationRunner`.

---

## 7. Interfaces Discord

```
interfaces/discord/
├── startup.py          # init_discord_jdr() — USE_ENGINE_V2, RuleEngine, SQLite
├── container.py        # DiscordJdrContext
├── settings.py         # DiscordSettings
├── handlers/           # 13 modules (character, dice, spell, combat_roll, mj_*, …)
├── views/              # creer_perso_wizard, level_up_choice, prepared_spells_choice
├── components/         # entity_select, point_buy, asi, …
├── formatters/         # character_embed, lore_text
└── permissions/        # mj.py
```

`interfaces/api/` et `interfaces/web/` **n'existent pas**.

---

## 8. `bot/` — points d'entrée Discord

**Actif au runtime** — le bot ne démarre pas sans les cogs.

`main.py` constante `COGS` (L80-90), chargement L119-125 :

| Cog | Rôle |
|---|---|
| `bot.cogs.dice` | `/roll` |
| `bot.cogs.character` | Fiche personnage (hybride legacy v1 + moteur v2) |
| `bot.cogs.spell` | `/sort`, `/preparer-sorts` |
| `bot.cogs.creation` | `/creer-perso` |
| `bot.cogs.rest` | Commandes MJ (repos, level-up, grimoire) |
| `bot.cogs.racial` | `/souffle` |

**Suppression interdite** (`AGENTS.md` §6.7). Les cogs délèguent aux handlers `interfaces/discord/` ; `bot/models/character.py` reste le modèle legacy v1 JSON.

---

## 9. Outils (`tools/`)

| Script | Rôle |
|---|---|
| `validate_compendium.py` | Validation L1-L5 |
| `migrate_persistence.py` | Migration personnages v1 → v2 (JSON) |
| `import_srd_mechanics.py` | Import mécaniques SRD → `definition.yaml` |
| `migrate_spells_b2.py` | Migration sorts v1.0 → v2.0 |

---

## 10. Tests et CI

```
tests/
├── unit/           (75 fichiers)
├── integration/    (test_character_lifecycle.py)
├── compendium/     (test_dnd5e_integrity.py)
└── helpers/        (creation, level_up)
```

Framework : **`unittest`** uniquement.

CI (`.github/workflows/ci.yml`, Python 3.12) :

```bash
python -m unittest discover -s tests -v
python tools/validate_compendium.py dnd5e
```

---

## 11. Arborescence réelle (extrait)

```
discord-jdr-bot/
├── main.py
├── AGENTS.md, VISION.md, ROADMAP.md, README.md
├── bot/                    # 6 cogs actifs
├── interfaces/discord/     # seule interface
├── jdr_engine/             # moteur pur
├── compendium/dnd5e/       # 166 entrées
├── data/bot.db             # SQLite runtime
├── fixtures/, scripts/
├── tools/                  # 4 scripts
├── tests/
└── docs/
    ├── ARCHITECTURE.md           # Ce document
    ├── ARCHITECTURE_TARGET.md      # Architecture cible
    └── adr/
```

---

## 12. Dépendances effectives

```
interfaces/discord  →  application/character_service
                    →  rules/engine
                    →  persistence/sqlite_character_repository

application         →  persistence, rules, domain

rules               →  compendium (loader, registry), domain

domain              →  (stdlib + intra-domain uniquement)
```

Pas de couche `game/`, pas d'`EventBus`, pas de `core/i18n` ni `core/plugins` dans le graphe réel.

---

*Document aligné sur le code au commit courant. Toute modification structurelle cible = [`ARCHITECTURE_TARGET.md`](ARCHITECTURE_TARGET.md) + ADR si décision actée.*
