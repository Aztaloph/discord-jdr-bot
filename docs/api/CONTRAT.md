# Contrat API HTTP — v1 (décisions structurantes)

| Attribut | Valeur |
|---|---|
| **Statut** | Accepté (arbitrages mainteneur 2026-08-07) |
| **Date** | 2026-08-07 |
| **Périmètre** | Décisions coûteuses à revenir en arrière une fois qu'un client consomme l'API |
| **Hors périmètre** | Spécification endpoint par endpoint, schémas champ par champ, catalogue d'erreurs exhaustif |

**Critère de tri** : une décision entre ici si la changer plus tard **casse un client existant** ou **impose une migration**. Tout le reste sera découvert à l'implémentation et est listé comme hors contrat.

**État de référence moteur** : 866 tests ; combat persistant (initiative, tours, attaques, sorts, conditions, concentration) ; registre d'effets unifié (ADR-006) ; API existante limitée au personnage hors combat (`interfaces/api/`, `docs/API_LOCAL.md`).

**Préfixe URL** : toutes les routes contractuelles vivent sous **`/v1/`**.

### Cadrage produit — API seule interface de jeu (2026-08-07)

**Décision mainteneur** : Discord n'est **plus** une interface de jeu. Il sert au **vocal** et, éventuellement, au **chat** (relay de messages vers l'API — transport, pas mécanique). Aucune mécanique de jeu (combat, jets, gestion de fiche) ne passera par Discord.

**Conséquences contractuelles** :

- L'**API HTTP** est le **seul client de jeu** ; pas de cohabitation avec un second point d'entrée sur les mêmes invariants.
- Tout développement visant une double utilisation API + Discord est **arrêté**.
- Le code Discord existant n'est **pas supprimé** dans le lot 1, mais **n'est plus une cible d'évolution** — ne rien y ajouter.
- Les invariants métier se posent **côté API** sans compatibilité Discord.

---

## 1. Frontière du modèle

### 1.1 Principe

L'API expose des **ressources** et des **résultats d'actions**. Elle n'expose pas les mécanismes internes de collecte, de résolution ni les structures de convenance du moteur Python.

Le vocabulaire exposé devient **contrat de stabilité** : tout identifiant string publié (`spell_id`, `condition_id`, `effect_id`, `ability_id`) engage sur la persistance sémantique de cette chaîne côté moteur et compendium.

### 1.2 Inventaire des concepts

| Concept interne | Traverse l'API ? | Forme côté client | Justification |
|---|---|---|---|
| **`Character`** (fiche SQLite) | **Oui** | Ressource `/v1/characters/{character_id}` ; agrégat calculé « fiche » (DTO existant `character_sheet_to_dict`, éventuellement enrichi — §2.6) | Source de vérité persistante hors rencontre (ADR-004 §1, ADR-005 sync-on-close) |
| **`Combatant`** (overlay rencontre) | **Oui** | Objet embarqué dans la ressource combat ; référencé par `combatant_id` dans les actions | PV/CA/tour/concentration overlay pendant le combat (ADR-004 §9) ; distinct de la fiche |
| **`CombatState`** | **Oui** (partiel) | Agrégat combat : statut, round, tour, ordre d'initiative, combattants, effets actifs | Snapshot sérialisable déjà persisté en blob SQLite |
| **`ActiveEffect`** | **Oui** (snapshot) | Liste `active_effects[]` avec les champs de `ActiveEffect.to_dict()` | État observable des buffs/conditions mécaniques ; mutations via actions API, pas via écriture directe |
| **`ActiveEffectRegistry`** | **Non** | — | Structure runtime (`CombatManager._effect_registries`) ; reconstruite à partir du blob + hydratation (`load_combat`) ; aucune opération client légitime sur le registre lui-même |
| **Collecteurs `collect_*`** (`rules/effects/collect.py`) | **Non** | — | Traduction registre → `effects[]` pour `d20.py` ; détail d'implémentation ADR-006 décision 3 |
| **Distinction attaquant / défenseur du collecteur** | **Non** (mécanisme) ; **Oui** (sémantique) | Les actions d'attaque prennent `attacker_id` + `target_id` (identifiants **combattant**) ; le client fournit le **contexte de portée** (`melee_weapon`, `ranged_weapon`) | Le paramètre interne `defender_id` de `roll_d20_for_combatant` est un détail de pipeline ; le contrat API reproduit la paire attaquant/cible + flags de requête |
| **`D20RollRequest`** | **Non** en entrée brute ; **Oui** en sortie partielle | Entrée : sous-ensemble explicite « contexte de jet » par type d'action ; Sortie : objet `d20` dans les résultats (DTO `_d20_result_to_dict`, sans `modifier_breakdown`) | Dataclass interne riche et évolutive |
| **`D20RollResult`** | **Oui** | Objet structuré dans la réponse d'action | Résultat métier ; déjà sérialisé pour l'API personnage |
| **`effect_id` / `source_id`** | **Oui** | Champs string dans `active_effects[]` et traces dans `applied_effects` | Vocabulaire moteur stable |
| **`EventBus` / événements domaine** | **Non** (contrat principal) | Option dev : tampon diagnostic (ex. `/debug/events`) non garanti en prod | Les clients métier lisent l'état post-action |
| **`RuleEngine` / compendium** | **Non** | Les réponses portent des **ids** et libellés déjà résolus | Pas d'introspection compendium générique en v1 |
| **`ActionBudget`** | **Oui** (lecture) ; **Non** (écriture directe) | Sous-objet du combattant en combat actif | Consommé par les actions ; pas de PATCH manuel |

### 1.3 Identifiants stables exposés

| Identifiant | Portée | Stabilité contractuelle |
|---|---|---|
| `character_id` | Persistant, cross-session | Stable — clé SQLite courte |
| `combat_id` | Rencontre | Stable — entier SQL auto-incrémenté |
| `combatant_id` | Rencontre | Stable **dans** la rencontre — opaque (UUID tronqué 8 car.) |
| `spell_id`, `condition_id`, `effect_id` | Ruleset / catalogue moteur | Stable |
| `ability_id`, `skill` | Ruleset | Stable — vocabulaire SRD 2014 |

### 1.4 Double source Character / Combatant — règle temporelle API

Alignement ADR-005 pour la **persistance** (non négociable) :

- **Pendant** `status ∈ {preparing, active}` : overlay `Combatant` fait foi pour le **moteur** combat.
- **Après** `close_combat` : sync PV fiche ; conditions/effets rencontre non propagés sur `Character`.
- **Vue API fiche** (§2.6) : pendant un combat actif, `GET /v1/characters/{id}/sheet` expose une **vue fusionnée** pour le parcours joueur — sans écrire l'overlay sur la fiche SQLite.

---

## 2. Modèle d'état et de session

### 2.1 Qui possède la session de combat

Le **serveur** possède l'état ; le client le **référence** par `combat_id` (entier) dans `/v1/combats/{combat_id}`.

Pas de session HTTP dédiée. Pas de sticky session en mémoire requise (blob SQLite + réhydratation registre à la demande).

### 2.2 Cycle de vie — alignement moteur strict

```
preparing → active → ended
```

| Transition moteur | Sémantique API |
|---|---|
| `create_combat` | `POST /v1/combats` — statut `preparing` |
| `add_combatant` | Ajout participant (**preparing** uniquement en v1 — voir §10) |
| `activate_combat` | `POST /v1/combats/{id}/activate` |
| Mutations combat | Actions POST sous `/v1/combats/{id}/…` |
| `close_combat` | `POST /v1/combats/{id}/close` |

Séquence `close_combat` (ADR-005, implémentée) — l'endpoint de clôture ne la réordonne pas :

1. Sync PV overlay → fiche
2. Réconciliation concentration overlay → fiche
3. Conditions : discard fiche (archive `active_effects` blob OK)
4. `status=ended`, persist, `CombatEnded`

### 2.3 Persistance

- **Durable** : blob `CombatState` + colonne SQL `status`.
- **Cache process** : `ActiveEffectRegistry` par `combat_id`, reconstruit depuis le blob.
- **Redémarrage serveur** : reprise depuis SQLite ; pas de perte si base intacte.

Modèle **stateless HTTP + état serveur durable**. Idempotence des POST **non** garantie en v1.

### 2.4 Concurrence

**Décision** : **last-writer-wins** — pas de `revision`, pas de `If-Match`, pas de file d'actions en v1.

Deux requêtes concurrentes sur le même `combat_id` ou `character_id` peuvent se recouvrir. Documenter l'interdiction d'accès parallèle non coordonné sur la même ressource.

**Alternative écartée** : verrou optimiste — reporté ; migration coûteuse une fois des clients en production.

### 2.5 Scope de création — body `POST /v1/combats`

Les champs `guild_id` et `channel_id` sont une **projection interne** du scope de persistance SQLite — **pas** du vocabulaire client.

| Champ | Statut |
|---|---|
| `character_ids` | **Obligatoire** |
| `channel_id` | **Optionnel** — généré côté serveur (UUID) si absent |
| `guild_id` | **Optionnel** — défaut serveur `"api"` ; jamais requis du client |

**Client minimal** :

```json
{ "character_ids": ["abc123", "def456"] }
```

Le serveur mappe en interne vers `create_combat(guild_id, channel_id, character_ids)` avec les valeurs par défaut ou générées.

**Parallélisme** : plusieurs combats ouverts simultanés via des `channel_id` distincts (générés ou fournis). L'index partiel SQLite `idx_combats_open_channel` limite à **un** combat ouvert par couple `(guild_id, channel_id)` — suffisant sans imposer des ids Discord réels.

**Invariant lobby (lot 1)** : voir §10.3 — un personnage ne peut être que dans **un** combat ouvert à la fois (`CHARACTER_ALREADY_IN_COMBAT`).

**Alternative écartée** : exiger `guild_id` + `channel_id` au client HTTP — rejetée (fuite du modèle Discord).

### 2.6 Fiche fusionnée pendant combat actif

**Décision (option B)** : `GET /v1/characters/{character_id}/sheet` retourne une **vue fusionnée** lorsque le personnage participe à un combat **ouvert** (`preparing` ou `active`) :

- **`hp_current`** (et champs overlay pertinents) ← combattant overlay ;
- **`active_effects`** (ou sous-ensemble contractuel) ← registre / snapshot combat pour ce `combatant_id` ;
- le reste ← fiche calculée habituelle.

La recherche du combat ouvert se fait **uniquement** par `character_id` — **sans** paramètre `combat_id` sur la route fiche. Cette unicité est garantie par l'invariant lobby (§10.3) : au plus un combat ouvert par personnage.

**Important** : fusion **lecture API uniquement** — la fiche SQLite reste au snapshot pré-sync (ADR-005) jusqu'à `close_combat`. Le client combat continue de lire `/v1/combats/{id}` pour l'état complet de rencontre.

**Alternative écartée** : fiche = SQLite seule pendant le combat — rejetée pour l'objectif parcours joueur unifié.

---

## 3. Format d'erreur

### 3.1 Structure unique

```json
{
  "error": {
    "code": "COMBAT_STATUS_INVALID",
    "message": "Les attaques ne sont possibles qu'en combat actif.",
    "details": {}
  }
}
```

| Champ | Obligatoire | Stabilité |
|---|---|---|
| `code` | Oui | Contrat — `SCREAMING_SNAKE_CASE` |
| `message` | Oui | Français ; non garanti stable |
| `details` | Non | Objet extensible |

Migration : l'API personnage actuelle (`detail` string) adopte ce format — breaking change assumé.

### 3.2 HTTP

| HTTP | Famille |
|---|---|
| **404** | Ressource absente |
| **409** | Règle métier / conflit d'état |
| **422** | Validation corps (`VALIDATION_ERROR`) |
| **500** | Erreur inattendue (`INTERNAL_ERROR`) |

### 3.3 Codes stables (minimum contractuel)

| Exception moteur | `code` |
|---|---|
| Personnage introuvable | `CHARACTER_NOT_FOUND` |
| Combat introuvable | `COMBAT_NOT_FOUND` |
| Combattant introuvable | `COMBATANT_NOT_FOUND` |
| `SpellCastError` | `SPELL_CAST_REJECTED` |
| `RestError` | `REST_REJECTED` |
| `CombatStatusError` | `COMBAT_STATUS_INVALID` |
| `UnknownCombatConditionError` | `UNKNOWN_CONDITION` |
| `ActionBudgetExhaustedError` | `ACTION_BUDGET_EXHAUSTED` |
| `OpenCombatExistsError` | `OPEN_COMBAT_EXISTS` |
| `InsufficientCombatantsError` | `INSUFFICIENT_COMBATANTS` |
| `NotCombatantTurnError` | `NOT_COMBATANT_TURN` |
| `CombatStateVersionError` | `COMBAT_STATE_UNSUPPORTED` |
| `require_spell_attack_type` | `SPELL_ATTACK_TYPE_MISSING` |
| Personnage déjà dans un combat ouvert | `CHARACTER_ALREADY_IN_COMBAT` |

---

## 4. Conventions de nommage et de versionnement

### 4.1 Chemins

- Préfixe **`/v1/`** sur toutes les routes contractuelles.
- Ressources plurielles snake_case : `/v1/characters`, `/v1/combats`.
- Actions : kebab-case — `/v1/combats/{id}/attack-roll`, `/v1/combats/{id}/close`.
- Diagnostic dev (`/debug/…`) hors contrat prod ; non préfixé ou explicitement exclu du contrat v1.

### 4.2 Champs JSON

snake_case ; vocabulaire SRD ; modes de jet `normal` / `avantage` / `desavantage` ; clés d'emplacements en string.

### 4.3 Versionnement

**Décision** : préfixe **`/v1/`** dès le premier lot implémentable. Ruptures futures → `/v2/` ; pas de version implicite.

---

## 5. Périmètre du premier lot implémentable

### 5.1 Parcours cible (bout-en-bout)

1. `GET /v1/characters/{id}/sheet` — fiche initiale
2. `POST /v1/combats` — body minimal `{ "character_ids": [...] }` ; vérification unicité lobby
3. `POST /v1/combats/{id}/activate`
4. `POST /v1/combats/{id}/attack-roll` — jet d'attaque avec contexte portée
5. `GET /v1/combats/{id}` — état rencontre
6. `GET /v1/characters/{id}/sheet` — **fiche fusionnée** (PV overlay, effets actifs)
7. `POST /v1/combats/{id}/close` — clôture + sync PV fiche

### 5.2 Ressources (intention, sans schémas)

| Intention | Route | Body (création) |
|---|---|---|
| Fiche (fusionnée si combat ouvert) | `GET /v1/characters/{character_id}/sheet` | — |
| Créer rencontre (lobby) | `POST /v1/combats` | `character_ids` obligatoire ; `channel_id`, `guild_id` optionnels |
| Lire rencontre | `GET /v1/combats/{combat_id}` | — |
| Activer | `POST /v1/combats/{combat_id}/activate` | — |
| Jet d'attaque | `POST /v1/combats/{combat_id}/attack-roll` | — |
| Clore | `POST /v1/combats/{combat_id}/close` | — |

**Tests lot 1 (commit 3)** : après `close`, les personnages du combat clos doivent pouvoir entrer dans un **nouveau** combat — l'invariant lobby ne doit pas les bloquer indéfiniment.

Routes personnage existantes (cast, repos) migrent sous `/v1/` avec le format d'erreur unifié.

**Hors lot 1** : sorts/conditions/dégâts combat, avancement de tour, création personnage, debug events.

---

## 6. Hors périmètre explicite (v1 contrat)

| Exclusion | Raison |
|---|---|
| Authentification / autorisation | Banc local |
| Rate limiting, pagination | Infra / volume |
| WebSocket / temps réel | Contrat transport distinct |
| OpenAPI comme contrat normatif | Ce document prime |
| CORS, déploiement multi-instance | Hors lot |
| Idempotency-Key, webhooks | Reportés |
| Introspection compendium | ids via moteur |
| Création / édition personnage | Autre lot |
| Action economy complète | Extension post-validation noyau |

---

## 7. Discord — hors périmètre jeu

Le code Discord (`bot/`, `interfaces/discord/`) reste en dépôt pour le vocal et le chat futur, mais **n'est plus une interface de jeu** (voir préambule). Aucune évolution Discord dans les lots API. Les handlers historiques (fiche, sorts, `/roll`) ne définissent pas le contrat v1.

---

## 8. État documentaire (post-résorption 2026-08-07)

| Point | Statut |
|---|---|
| ADR-004/006 conditions → registre | ADR realignés |
| Collecteur `rules/effects/collect.py` | ADR realignés |
| `close_combat` vs ADR-005 | ADR-005 complété (§ état implémenté) |
| Format erreur API | Migration prévue lot 1 |
| Endpoints combat | Lot 1 à implémenter |
| Tests référence AGENTS.md (645) | **866** mesurés — doc canonique non mise à jour dans ce lot |

---

## 9. Synthèse des décisions

| # | Décision | Statut |
|---|---|---|
| 1 | Ressources Character + Combat (+ ActiveEffect snapshot) | Tranché |
| 2 | Registre, collecteurs, D20RollRequest complet : internes | Tranché |
| 3 | Session = `combat_id` + SQLite | Tranché |
| 4 | Cycle de vie moteur strict | Tranché |
| 5 | Concurrence last-writer-wins | Tranché |
| 6 | Format erreur structuré | Tranché |
| 7 | Métier → 409, not found → 404 | Tranché |
| 8 | snake_case, ids SRD stables | Tranché |
| 9 | Préfixe `/v1/` | Tranché |
| 10 | Body création : `character_ids` seul requis ; scope interne | Tranché |
| 11 | Fiche fusionnée ; unicité combat ouvert par personnage | Tranché |
| 12 | Invariant lobby — `CHARACTER_ALREADY_IN_COMBAT` (lot 1) | Tranché |
| 13 | API seule interface de jeu ; Discord hors évolution | Tranché |

---

## 10. Réserves architecturales

### 10.1 Modèle cible — lobby

**Modèle produit** : un combat est un **lobby** que les joueurs rejoignent et quittent.

| Règle | Lot 1 | Plus tard |
|---|---|---|
| Un personnage ≤ un combat **ouvert** à la fois | **Oui** — `CHARACTER_ALREADY_IN_COMBAT` à l'entrée (couche API, sans modifier le moteur) | — |
| Tant qu'il est dans un lobby, pas d'interaction avec un autre combat | Implicite via unicité | — |
| Rejoindre un combat **déjà `active`** | Non | `POST /v1/combats/{id}/combatants` (moteur : extension `add_combatant`) |
| Sortir par **fuite** (action de jeu, jet possible) | Non | Chantier gameplay |

**Lot 1** : vérification API — requête sur les combats ouverts contenant le `character_id` avant `create_combat` / `add_combatant`. **Ne pas modifier** `CombatManager` pour cet invariant.

**Clôture** : `close_combat` passe le statut SQL à `ended` — le personnage est **libéré**. Test obligatoire (commit 3) : personnages réutilisables dans un nouveau combat après `close`.

### 10.2 Rejoindre un combat déjà `active`

Voir §10.1. `add_combatant` moteur n'accepte aujourd'hui que `preparing` ; le contrat ne fige pas la liste des combattants comme immuable après `activate`.

### 10.3 Scope repository

L'unicité `(guild_id, channel_id)` pour combats ouverts reste en base ; l'API masque ce détail via defaults et génération de `channel_id`. Assouplir l'unicité globale = chantier repository distinct, **non requis** lot 1.

---

## Références

- `docs/adr/ADR-004-modele-combat.md` — conditions, registre
- `docs/adr/ADR-005-transition-fin-rencontre.md` — sync-on-close
- `docs/adr/ADR-006-modele-effets-actifs.md` — ActiveEffect
- `docs/API_LOCAL.md` — API personnage actuelle (à migrer `/v1/` + erreurs)
- `jdr_engine/game/combat_manager.py`
- `jdr_engine/rules/effects/collect.py`
- `jdr_engine/application/dto/output_serializers.py`
- `interfaces/api/app.py`
