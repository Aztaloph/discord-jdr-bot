# Architecture cible — Moteur JDR modulaire

> **Document cible — rien de ce qui suit n'est implémenté tel que décrit**, sauf renvoi explicite vers [`ARCHITECTURE.md`](ARCHITECTURE.md) pour l'existant partiel.
>
> Rédigé au **futur** ou au **conditionnel**. Ne pas utiliser ce fichier pour déduire l'état du dépôt.
>
> État réel vérifié : [`ARCHITECTURE.md`](ARCHITECTURE.md).

| Attribut | Valeur |
|---|---|
| **Version** | 2.0 |
| **Date** | 2026-07-27 |
| **Statut** | Architecture cible — implémentation partielle en cours |
| **ADRs associés** | ADR-001, ADR-002, ADR-003 |

---

## 1. Vision

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERFACES                                │
│  Discord · Web · Mobile · CLI · API REST · Foundry VTT      │
└──────────────────────────┬──────────────────────────────────┘
                           │ Commands / Queries / Events ↓↑
┌──────────────────────────▼──────────────────────────────────┐
│                  APPLICATION LAYER                           │
│         Services (Use Cases) + EventBus subscribers          │
└──────┬───────────────┬───────────────┬───────────────────────┘
       │               │               │
┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐ ┌─────────────┐
│ GAME ENGINE │ │ RULE ENGINE │ │ PERSISTENCE │ │   PLUGINS   │
│   (état)    │ │  (calcul)   │ │    (I/O)    │ │ (extensions)│
└──────┬──────┘ └──────┬──────┘ └─────────────┘ └─────────────┘
       │               │
       └───────┬───────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│                      COMPENDIUM                                │
│  definition.yaml · lore · i18n · assets · meta · docs       │
└───────────────────────────────────────────────────────────────┘
```

**Principe fondateur :** le moteur ne devra pas connaître Discord, D&D, ni aucune entité de jeu par son nom. Il ne connaîtra que des **mécanismes** et des **identifiants**.

---

## 2. Les sept piliers

Répartition visée des responsabilités :

| Pilier | Package | Rôle visé | Stateful |
|---|---|---|---|
| **Domain** | `jdr_engine/domain/` | Entités, value objects, invariants | Définira l'état |
| **Compendium** | `compendium/` + `jdr_engine/compendium/` | Données statiques, loader, presenter | Cache RO |
| **Rule Engine** | `jdr_engine/rules/` | Validation, résolution, calcul | ❌ |
| **Game Engine** | `jdr_engine/game/` | Transitions d'état, machines à états | ✅ |
| **Persistence** | `jdr_engine/persistence/` | Repositories, migrations | I/O |
| **Core** | `jdr_engine/core/` | EventBus, i18n, assets, plugins, config | Infrastructure |
| **Interfaces** | `interfaces/` | Adapters plateforme | Session UI |

---

## 3. Compendium — structure enrichie

### 3.1 Philosophie

Le Compendium n'est **pas** une collection de JSON. C'est une **base documentaire** par entité de jeu :

| Fichier | Lu par le moteur ? | Usage |
|---|---|---|
| `definition.yaml` | ✅ **Oui** | Mécaniques pures (Rule Engine) |
| `meta.yaml` | ⚠️ Partiel | Tags, auteur, source SRD, date |
| `lore.{locale}.md` | ❌ Non | Descriptions UI (Discord, Web) |
| `assets/portrait.png` | ❌ Non | Illustrations UI |
| `assets/icon.svg` | ❌ Non | Icônes menus |
| `docs/` | ❌ Non | Documentation auteur / MJ |

### 3.2 Arborescence complète

```
compendium/
│
├── schemas/                           # JSON Schema réels (validation L4)
│   ├── race-mechanics.schema.json
│   └── class-mechanics.schema.json
│                                      # chargés par jdr_engine/compendium/mechanics_schema.py
│
├── _schemas/                          # vide (.gitkeep) — non lu par le moteur
│
├── dnd5e/                             # Ruleset D&D 5e SRD
│   ├── manifest.yaml                  # id, version, schema_version, locales
│   ├── config.yaml                    # Ability names, level table, currencies
│   │
│   └── entries/
│       ├── races/
│       │   └── elf/
│       │       ├── definition.yaml    # ★ Moteur
│       │       ├── meta.yaml          # source: SRD, tags: [humanoid, fey]
│       │       ├── lore.fr.md
│       │       ├── lore.en.md
│       │       └── assets/
│       │           ├── portrait.png
│       │           └── icon.svg
│       │
│       ├── classes/fighter/...
│       ├── spells/fireball/...
│       ├── weapons/longsword/...
│       ├── armor/chain_mail/...
│       ├── conditions/poisoned/...
│       ├── monsters/goblin/...
│       ├── feats/...
│       ├── skills/...
│       ├── backgrounds/...
│       ├── languages/...
│       ├── traits/darkvision/...
│       └── actions/attack/...
│
├── dnd2024/                           # Futur ruleset
├── pathfinder2/                       # Futur ruleset
│
└── homebrew/                          # Contenu custom (optionnel, gitignored)
    └── my-campaign/
        └── entries/...
```

### 3.3 manifest.yaml (ruleset)

```yaml
id: dnd5e
name:
  fr: "Dungeons & Dragons 5e"
  en: "Dungeons & Dragons 5e"
version: "1.0.0"                    # Version sémantique du contenu
schema_version: "1.0"               # Version du schéma definition.yaml
compatible_engine: ">=0.1.0"        # Version moteur requise
locales: [fr, en]
default_locale: fr
license: SRD
entry_types:                         # au pluriel, tels que lus par le loader
  - races
  - classes
  - traits
  - spells
dependencies: []                     # Autres rulesets requis (ex: srd-core)
```

Exemple de manifest cible (les valeurs évolueront avec le ruleset).

### 3.4 Séparation moteur / UI (rappel ADR-002)

```
RuleEngine.get_entity("race", "elf")
  → lira UNIQUEMENT definition.yaml

CompendiumPresenter.get_lore("race", "elf", locale="fr")
  → lira lore.fr.md

AssetResolver.resolve_path("race", "elf", "portrait.png")   # -> Path | None
AssetResolver.resolve_portrait("race", "elf")               # -> Path | None
AssetResolver.reference("race", "elf", "portrait.png")      # -> AssetReference
  → déléguera à CompendiumPresenter.get_asset_path()
```

Le résolveur retournera un `Path` local (ou `None`), pas une URL. État partiel aujourd'hui : [`ARCHITECTURE.md`](ARCHITECTURE.md) §3.

---

## 4. Internationalisation (i18n)

Le module `jdr_engine/core/i18n/` n'existe pas encore. La cible prévoit :

### 4.1 Stratégie : **fichiers par locale**, pas clés dans le YAML

| Donnée | Mécanisme visé |
|---|---|
| Noms d'entités (race, classe…) | `definition.yaml → name.fr / name.en` (court) |
| Descriptions longues | `lore.fr.md`, `lore.en.md` (séparés) |
| Labels UI Discord | `jdr_engine/core/i18n/ui/` (fichiers `.yaml` par interface) |
| Messages d'erreur moteur | Codes d'erreur + catalogue i18n |
| Config système | `config.yaml → abilities[].name.fr / .en` |

### 4.2 Module `jdr_engine/core/i18n/`

```
core/i18n/
  ├── translator.py          # t("error.character.not_found", locale="fr")
  ├── locale_resolver.py     # Détecte locale joueur / serveur / défaut
  └── catalogs/
      ├── engine.fr.yaml       # Erreurs moteur
      ├── engine.en.yaml
      └── discord.fr.yaml      # Labels boutons, embeds génériques
```

### 4.3 Règles

- Le **Rule Engine** retournera des **identifiants** + noms localisés si demandé
- Les **Interfaces** choisiront la locale (pref utilisateur Discord, header HTTP, flag CLI)
- Fallback : `default_locale` du manifest → `en`
- Le contenu compendium **non traduit** → fallback locale + warning validation

### 4.4 CompendiumSelect (Discord)

```python
# Générera automatiquement :
# ▼ Elfe (Elf)     ← name.fr + name.en en description si multilingue
options = compendium_service.list_for_select("race", locale=user_locale)
```

`CompendiumService` n'existera qu'à la livraison de cette couche.

---

## 5. Gestion des assets

`AssetResolver` existe partiellement (`resolver.py` seul). La cible complétera :

### 5.1 Module `jdr_engine/core/assets/`

```
core/assets/
  ├── resolver.py            # Résoudra chemin local → URL publique
  ├── registry.py              # Indexera assets par entité
  └── protocols.py             # AssetProvider (local, CDN, S3…)
```

### 5.2 Convention

```
entries/races/elf/assets/
  portrait.png       # 256×256, fiche personnage
  icon.svg           # 32×32, menus
  token.png          # 70×70, combat tracker (futur VTT)
  banner.jpg         # 600×200, embed header (optionnel)
```

### 5.3 Providers (Strategy pattern)

| Provider | Usage |
|---|---|
| `LocalAssetProvider` | Dev, bot auto-hébergé — fichiers locaux |
| `CDNAssetProvider` | Prod — URLs Cloudflare/R2 |
| `DiscordCDNProvider` | Upload auto portrait → URL Discord (optionnel) |

### 5.4 Règle

Le moteur **ne chargera jamais** les images. Il retournera un `AssetReference { entity_type, entity_id, asset_name }`. L'interface résoudra l'URL.

---

## 6. EventBus

L'EventBus n'existe pas. Voir **ADR-003** pour le raisonnement complet.

### 6.1 Placement visé

```
jdr_engine/core/events/
  ├── bus.py                   # EventBus impl (sync in-process)
  ├── registry.py              # Subscribe / unsubscribe
  ├── domain_events/           # Un fichier par catégorie
  │   ├── character.py
  │   ├── combat.py
  │   ├── inventory.py
  │   └── progression.py
  └── handlers/                # Handlers internes moteur (auto-save, audit)
      ├── audit_log.py
      └── auto_save.py
```

### 6.2 Interfaces s'abonneront au boot

```python
# interfaces/discord/startup.py (cible)
event_bus.subscribe(AttackResolved, discord_combat_handler.on_attack)
event_bus.subscribe(CharacterCreated, discord_character_handler.on_created)
```

État actuel de `startup.py` : [`ARCHITECTURE.md`](ARCHITECTURE.md) §5 et §7.

---

## 7. Système de plugins / extensions

Le système de plugins n'existe pas. La cible prévoira :

### 7.1 Objectif

Permettre d'étendre le moteur **sans modifier le core** :

- Règles maison (critique explosé custom)
- Intégrations (Roll20, Spotify ambiance)
- Contenu homebrew packagé
- Handlers EventBus supplémentaires

### 7.2 Architecture plugin

```
plugins/
  └── my-critical-hits/
      ├── plugin.yaml              # Manifest plugin
      ├── handlers.py              # EventBus handlers
      └── compendium/              # Entrées homebrew optionnelles
          └── entries/...
```

```yaml
# plugin.yaml
id: my-critical-hits
name: "Critical Hits Extended"
version: "1.0.0"
engine_version: ">=0.5.0"
rulesets: [dnd5e]                   # Compatible avec
entry_point: handlers:register     # Fonction appelée au boot
events:
  subscribe: [AttackResolved]
permissions:
  - publish_events
  - register_compendium_entries
```

### 7.3 PluginManager (`jdr_engine/core/plugins/`)

```
core/plugins/
  ├── manager.py               # Découverte, chargement, lifecycle
  ├── manifest.py              # Schéma plugin.yaml
  └── sandbox.py               # Restrictions (pas d'import discord)
```

### 7.4 Règles de sécurité

| Autorisé plugin | Interdit plugin |
|---|---|
| S'abonner EventBus | Importer discord.py |
| Enregistrer entrées compendium homebrew | Accès direct persistence |
| Publier événements custom | Modifier le registry core |

### 7.5 Alternative rejetée : plugins Python arbitraires exécutables

Trop risqué (code arbitraire). Les plugins v1 sont des **handlers typés** + **compendium homebrew** — pas d'exécution de logique métier libre.

---

## 8. Validation avancée du Compendium

Les niveaux L1-L5 existent partiellement — voir [`ARCHITECTURE.md`](ARCHITECTURE.md) §4. La cible ajoutera :

### 8.1 Niveaux de validation (compléments visés)

| Niveau | Quand | Comportement visé |
|---|---|---|
| **L4 — Sémantique** | CI | Level 1 fighter a hit_die valide |
| **L5 — Assets** | CI (warn) | portrait.png référencé existe |
| **L6 — i18n** | CI (warn) | lore.fr.md présent si locale déclarée |

(L1-L3 et une forme de L4/L5 JSON Schema sont déjà livrés — détail dans `ARCHITECTURE.md`.)

### 8.2 Modes de boot

| Mode | Env | Comportement visé |
|---|---|---|
| `strict` | dev, CI | Échouera si L1-L4 échoue |
| `warn` | prod | Loggera un warning, exclura entrées invalides |
| `off` | tests unitaires | Ignorera la validation |

Sélection par variable d'environnement.

### 8.3 Outil CLI

```bash
python tools/validate_compendium.py dnd5e --level 4 --locale fr
python tools/validate_compendium.py --all --strict
```

CLI actuel (ruleset + `--warn` uniquement) : [`ARCHITECTURE.md`](ARCHITECTURE.md) §4.

### 8.4 Rapport

```
✅ dnd5e — 847 entries validated
⚠️  3 warnings (missing lore.en.md for spells/xxx)
❌ 1 error (broken ref: classes/fighter → traits/nonexistent)
```

---

## 9. Versionnement des règles

### 9.1 Trois niveaux de version

| Version | Portée | Exemple visé |
|---|---|---|
| **schema_version** | Format `definition.yaml` | `"1.0"` → ajout champ `effects` = `"1.1"` |
| **ruleset version** | Contenu d'un ruleset | `dnd5e@1.2.0` |
| **engine version** | API moteur Python | `jdr_engine@0.3.0` |

### 9.2 Personnage lié à un ruleset versionné

```yaml
# Personnage persisté (cible)
ruleset_id: dnd5e
ruleset_version: "1.2.0"    # Version au moment de la création
schema_version: "1.0"
```

Champs partiellement livrés aujourd'hui (`ruleset_id`, `ruleset_version`, `schema_version`) : [`ARCHITECTURE.md`](ARCHITECTURE.md) §5.

### 9.3 Politique de compatibilité

| Changement ruleset | Impact |
|---|---|
| Patch (1.2.0 → 1.2.1) | Correction typo lore → transparent |
| Minor (1.2 → 1.3) | Nouvelle race → transparent |
| Major (1.x → 2.0) | Refonte fighter → **migration personnage** |

### 9.4 RuleEngine multi-version

```
CompendiumRegistry
  ├── dnd5e@1.2.0  (chargé)
  ├── dnd5e@1.3.0  (chargé)
  └── dnd5e@latest → 1.3.0

RuleEngine.for_character(character)
  → utilisera ruleset_id + ruleset_version du personnage
```

---

## 10. Multi-rulesets simultanés

### 10.1 Scénarios supportés

| Scénario | Support visé |
|---|---|
| Serveur Discord D&D 5e + serveur Pathfinder | ✅ |
| Campagne utilisant dnd5e + homebrew pack | ✅ |
| Même personnage, deux rulesets | ❌ (un personnage = un ruleset) |
| MJ compare deux rulesets | ✅ (CompendiumService) |

### 10.2 Registry multi-ruleset

```python
registry = CompendiumRegistry()
registry.load("dnd5e")
registry.load("pathfinder2")
registry.load("homebrew/my-campaign")

engine = RuleEngine(registry, ruleset_id="dnd5e", version="1.2.0")
```

État actuel (un seul ruleset, `RuleEngine.load()`) : [`ARCHITECTURE.md`](ARCHITECTURE.md) §3.

### 10.3 Config par serveur (Discord)

```json
// config.json (futur)
{
  "guild_id": 123,
  "default_ruleset": "dnd5e",
  "default_locale": "fr"
}
```

---

## 11. Persistence & migrations

### 11.1 Structure

```
jdr_engine/persistence/
  ├── protocols.py
  ├── character_repository.py
  ├── combat_repository.py
  └── migrations/
      ├── runner.py              # Exécute migrations pending
      ├── registry.py            # Liste ordonnée des migrations
      └── versions/
          ├── 001_initial.py
          ├── 002_v1_to_v2_character.py
          └── 003_add_ruleset_version.py
```

État actuel (SQLite, `database.py`, `v1_to_v2.py`) : [`ARCHITECTURE.md`](ARCHITECTURE.md) §5 — hors périmètre de cette structure cible.

> **Persistance combat** : [ADR-004](adr/ADR-004-modele-combat.md) fait autorité (table `combats` dans `data/bot.db` — pas de répertoire `data/combats/`).

### 11.2 Contrat migration

```python
class Migration(Protocol):
    version: int
    description: str
    def up(self, data_dir: Path) -> None: ...
    def down(self, data_dir: Path) -> None: ...  # Rollback
```

### 11.3 metadata persistance

```json
// data/_meta.json
{
  "persistence_version": 3,
  "migrated_at": "2026-07-02T14:00:00Z"
}
```

### 11.4 Règles

- Backup automatique avant migration
- Migration **idempotente** si possible
- Tests integration par migration
- `down()` obligatoire pour les migrations réversibles

---

## 12. Rule Studio & outils (`tools/`)

### 12.1 Vision Rule Studio

Assistant interactif CLI ( puis Web ) pour créer du contenu **sans éditer YAML** :

```
$ python tools/rule_studio.py create race

? Ruleset: dnd5e
? ID: orc
? Nom (FR): Orc
? Nom (EN): Orc
? Bonus caractéristiques: str +2, con +1
? Traits: darkvision, aggressive
? Vitesse: 30
? Générer lore.fr.md depuis template ? [Y/n]

✅ Créé: compendium/dnd5e/entries/races/orc/
✅ Validation: OK
```

### 12.2 Outils planifiés

| Outil | Rôle |
|---|---|
| `validate_compendium.py` | Validation L1-L6 (cible) — partiellement livré, voir `ARCHITECTURE.md` §4 |
| `import_srd_mechanics.py` | Import SRD — livré, voir `ARCHITECTURE.md` §9 |
| `migrate_spells_b2.py` | Migration sorts v2.0 — livré, voir `ARCHITECTURE.md` §9 |
| `rule_studio.py` | Assistant création générique |
| `create_race.py` | Raccourci race |
| `create_spell.py` | Raccourci sort (niveau, école, composantes…) |
| `create_monster.py` | Raccourci monstre (CR, actions…) |
| `create_item.py` | Arme, armure, objet magique |
| `migrate_persistence.py` | Migrations données — livré, voir `ARCHITECTURE.md` §9 |
| `generate_docs.py` | Documentation auto (§13) |
| `pack_ruleset.py` | Export zip d'un ruleset (partage) |

---

## 13. Génération automatique de documentation

### 13.1 Objectif

Produire de la doc à jour depuis le Compendium — jamais manuelle.

### 13.2 Outputs

```
docs/generated/
  ├── dnd5e/
  │   ├── index.md                 # Liste toutes les entités
  │   ├── races.md                 # Table races + stats
  │   ├── classes.md
  │   ├── spells/                  # Un md par sort
  │   │   └── fireball.md
  │   └── monsters/
  └── compendium-stats.json        # Compteurs, dernière génération
```

### 13.3 Sources

| Généré depuis | Contenu doc |
|---|---|
| `definition.yaml` | Tableaux stats, effets |
| `lore.{locale}.md` | Description narrative |
| `meta.yaml` | Source, tags, auteur |
| `manifest.yaml` | Version ruleset |

### 13.4 Intégration CI

```yaml
# Futur .github/workflows/docs.yml
- run: python tools/generate_docs.py dnd5e
- run: git diff --exit-code docs/generated/  # Fail si doc stale
```

---

## 14. Arbre complet V2

```
discord-jdr-bot/
├── pyproject.toml
├── requirements.txt                     # dépendances installées par la CI
├── main.py
├── AGENTS.md                            # état réel du dépôt — référence des agents
├── VISION.md
├── ROADMAP.md
├── README.md
│
├── .github/workflows/ci.yml             # tests + validation du Compendium
│
├── jdr_engine/                          # ★ MOTEUR (zero discord)
│   ├── domain/
│   ├── compendium/                      # Loader, registry, presenter
│   ├── rules/                           # Rule Engine
│   ├── game/                            # Game Engine
│   ├── application/                     # Services
│   ├── persistence/                     # Repos + migrations
│   ├── dice/
│   └── core/
│       ├── events/                      # EventBus
│       ├── i18n/                        # Translator
│       ├── assets/                      # AssetResolver
│       ├── plugins/                       # PluginManager
│       └── config/                      # Settings, feature flags
│
├── compendium/                          # ★ DONNÉES
│   ├── schemas/                         # JSON Schema réels (race / class mechanics)
│   ├── _schemas/                        # vide (.gitkeep)
│   ├── dnd5e/
│   ├── dnd2024/
│   ├── pathfinder2/
│   └── homebrew/
│
├── interfaces/
│   ├── discord/
│   ├── api/                             # Futur FastAPI
│   ├── cli/                             # Futur
│   └── web/                             # Futur
│
├── plugins/                             # Extensions tierces
│
├── tools/                               # Rule Studio, validateurs
│
├── scripts/                             # seeds de personnages de démonstration
│
├── fixtures/                            # personnages v2 de référence (seed / tests)
│
├── data/                                # État runtime (gitignored)
│   ├── bot.db
│   ├── characters/
│   ├── combats/                         # cible historique — persistance actée : voir [ADR-004](adr/ADR-004-modele-combat.md)
│   └── _meta.json
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── compendium/
│   └── helpers/                         # fabriques partagées (creation, level_up)
│
├── docs/
│   ├── ARCHITECTURE.md                # État actuel (réel)
│   ├── ARCHITECTURE_TARGET.md         # Ce document
│   ├── adr/                             # Architecture Decision Records
│   └── generated/                       # Doc auto-générée
│
└── bot/                                 # LEGACY — migration vers interfaces/discord (Phase 10)
```

Arbre cible. État réel du dépôt (dont `bot/` actif au runtime) : [`ARCHITECTURE.md`](ARCHITECTURE.md) §8 et §11.

---

## 15. Dépendances entre modules (V2)

```
interfaces/*  →  application  →  game  →  domain
                    │              │
                    ├── rules  →  compendium (loader)
                    │              │
                    ├── persistence
                    │
                    └── core/events  (publish/subscribe)

interfaces/*  →  core/i18n, core/assets, core/plugins
plugins/*     →  core/events, compendium (homebrew entries)
tools/*       →  compendium/schemas, compendium (validate)

domain        →  (RIEN — centre pur)
```

---

## 16. Interfaces publiques (résumé V2)

Couche applicative cible. Déjà livré : `RuleEngine`, `CharacterService`, `AssetResolver` — [`ARCHITECTURE.md`](ARCHITECTURE.md) §3 et §6.

| Interface | Package | Consommateurs visés |
|---|---|---|
| `RuleEngine` | `jdr_engine/rules/engine.py` | Application services |
| `CompendiumService` | `jdr_engine/application/` | Interfaces, tools |
| `CharacterService` | `jdr_engine/application/` | Discord, API |
| `CombatService` | `jdr_engine/application/` | Discord, API |
| `EventBus` | `jdr_engine/core/events/bus.py` | Game Engine, Interfaces, Plugins |
| `AssetResolver` | `jdr_engine/core/assets/` | Interfaces |
| `Translator` | `jdr_engine/core/i18n/` | Interfaces, tools |
| `PluginManager` | `jdr_engine/core/plugins/` | Boot (main.py) |
| `MigrationRunner` | `jdr_engine/persistence/migrations/` | tools, boot |

---

## 17. Roadmap V2 (révisée)

**Cette numérotation « Phase 0-10 » n'a aucun équivalent dans le dépôt.** La planification opérationnelle réelle vit dans `ROADMAP.md`, qui emploie `ÉTAPE 1a` à `ÉTAPE 9`, des `Axe A` / `Axe B`, des `Lot` et des `Passe` — le mot « Phase » n'y apparaît pas. Le tableau ci-dessous est conservé comme trace de la découpe technique envisagée à la rédaction ; pour savoir quoi livrer et dans quel ordre, se référer à `ROADMAP.md`.

| Phase | Contenu | Nouveau V2 |
|---|---|---|
| **0** | Fondations, dice déplacé | + `docs/adr/`, structure `core/` |
| **1** | Compendium + Rule Engine MVP | + validation L1-L3, manifest versionné |
| **2** | Domain + Persistence v2 | + migrations framework, ruleset_version |
| **3** | Discord selects | + i18n locale, AssetResolver local |
| **4** | Affichage fiche calculée | + lore.md dans embeds, portraits |
| **5** | Backgrounds, skills | + Rule Studio `create_race` |
| **6** | RollService | |
| **6b** | **EventBus** | Publish domain events, Discord handlers |
| **7** | Combat MVP | EventBus combat, auto-save handler |
| **8** | Contenu massif | + generate_docs, validate L4-L6 |
| **8b** | **Plugins v1** | PluginManager, homebrew pack |
| **9** | API REST | EventBus → WebSocket |
| **10** | Nettoyage legacy | |

---

## 18. Risques V2 (additions)

| Risque | Mitigation |
|---|---|
| i18n incomplète | Fallback + validation warn |
| Assets lourds (repo size) | Git LFS ou CDN provider |
| Plugins malveillants | Sandbox v1 restrictive |
| Multi-ruleset confusion UI | Ruleset explicite par serveur |
| Doc générée stale | CI check |
| EventBus handler lent | Timeout + async option |

---

## 19. Décisions validées (récap)

| # | Décision | Document |
|---|---|---|
| 1 | Compendium unifié (pas de double `rules/`) | ADR-002 |
| 2 | Rule Engine stateless, data-driven | ADR-001 |
| 3 | EventBus in-process typé | ADR-003 |
| 4 | Validation strict (dev/CI) + warn (prod) | §8.2 |
| 5 | Format YAML pour `definition.yaml` | §3 |
| 6 | i18n par fichiers locale | §4 |
| 7 | Assets via AssetReference, pas chargés moteur | §5 |
| 8 | Personnage = IDs + choix, stats calculées | ADR-002 |
| 9 | Plugins = handlers + homebrew, pas code arbitraire | §7 |
| 10 | Migration progressive (Strangler Fig) | §17 |

---

## 20. Prochaine étape

La planification opérationnelle est dans [`ROADMAP.md`](../ROADMAP.md). L'état d'implémentation courant est décrit dans [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

*Document maintenu par le Lead Architect. Toute modification structurelle = nouvel ADR.*
