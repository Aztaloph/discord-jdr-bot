# Contrat API HTTP — v1 (décisions structurantes)

| Attribut | Valeur |
|---|---|
| **Statut** | Proposition — aucune implémentation engagée par ce document |
| **Date** | 2026-08-07 |
| **Périmètre** | Décisions coûteuses à revenir en arrière une fois qu'un client consomme l'API |
| **Hors périmètre** | Spécification endpoint par endpoint, schémas champ par champ, catalogue d'erreurs exhaustif |

**Critère de tri** : une décision entre ici si la changer plus tard **casse un client existant** ou **impose une migration**. Tout le reste sera découvert à l'implémentation et est listé comme hors contrat.

**État de référence moteur** : 866 tests ; combat persistant (initiative, tours, attaques, sorts, conditions, concentration) ; registre d'effets unifié (ADR-006) ; API existante limitée au personnage hors combat (`interfaces/api/`, `docs/API_LOCAL.md`).

---

## 1. Frontière du modèle

### 1.1 Principe

L'API expose des **ressources** et des **résultats d'actions**. Elle n'expose pas les mécanismes internes de collecte, de résolution ni les structures de convenance du moteur Python.

Le vocabulaire exposé devient **contrat de stabilité** : tout identifiant string publié (`spell_id`, `condition_id`, `effect_id`, `ability_id`) engage sur la persistance sémantique de cette chaîne côté moteur et compendium.

### 1.2 Inventaire des concepts

| Concept interne | Traverse l'API ? | Forme côté client | Justification |
|---|---|---|---|
| **`Character`** (fiche SQLite) | **Oui** | Ressource `/characters/{character_id}` ; agrégat calculé « fiche » (DTO existant `character_sheet_to_dict`) | Source de vérité persistante hors rencontre (ADR-004 §1, ADR-005 sync-on-close) |
| **`Combatant`** (overlay rencontre) | **Oui** | Objet embarqué dans la ressource combat ; référencé par `combatant_id` dans les actions | PV/CA/tour/concentration overlay pendant le combat (ADR-004 §9) ; distinct de la fiche |
| **`CombatState`** | **Oui** (partiel) | Agrégat combat : statut, round, tour, ordre d'initiative, combattants, effets actifs | Snapshot sérialisable déjà persisté en blob SQLite |
| **`ActiveEffect`** | **Oui** (snapshot) | Liste `active_effects[]` avec les champs de `ActiveEffect.to_dict()` | État observable des buffs/conditions mécaniques ; mutations via actions API, pas via écriture directe |
| **`ActiveEffectRegistry`** | **Non** | — | Structure runtime (`CombatManager._effect_registries`) ; reconstruite à partir du blob + hydratation (`load_combat`) ; aucune opération client légitime sur le registre lui-même |
| **Collecteurs `collect_*`** (`rules/effects/collect.py`) | **Non** | — | Traduction registre → `effects[]` pour `d20.py` ; détail d'implémentation ADR-006 décision 3 |
| **Distinction attaquant / défenseur du collecteur** | **Non** (mécanisme) ; **Oui** (sémantique) | Les actions d'attaque prennent `attacker_id` + `target_id` (identifiants **combattant**) ; le client fournit le **contexte de portée** (`melee_weapon`, `ranged_weapon`) | Le paramètre interne `defender_id` de `roll_d20_for_combatant` est un détail de pipeline ; le contrat API reproduit la paire attaquant/cible + flags de requête, comme le ferait un handler d'arme |
| **`D20RollRequest`** | **Non** en entrée brute ; **Oui** en sortie partielle | Entrée : sous-ensemble explicite « contexte de jet » par type d'action ; Sortie : objet `d20` dans les résultats (DTO `_d20_result_to_dict`, sans `modifier_breakdown`) | Dataclass interne riche et évolutive ; l'exposer entièrement en POST lierait chaque client à chaque nouveau flag traits/features |
| **`D20RollResult`** | **Oui** | Objet structuré dans la réponse d'action (rolls, mode, total, `applied_effects`, etc.) | Résultat métier ; déjà sérialisé pour l'API personnage |
| **`effect_id` / `source_id`** | **Oui** | Champs string dans `active_effects[]` et traces dans `applied_effects` | Vocabulaire moteur stable : `effect_id` = type d'effet (`blessed`, `prone`, `hunters_mark`…) ; `source_id` = origine (lanceur, ou la condition elle-même pour `expiry_mode=manual`) |
| **`EventBus` / événements domaine** | **Non** (contrat principal) | Option dev : tampon diagnostic (ex. `/debug/events` actuel) non garanti en prod | Les clients métier lisent l'état post-action, pas le bus ; le journal C7 (`CombatLogEntry`) pourrait devenir ressource séparée plus tard — hors v1 |
| **`RuleEngine` / compendium** | **Non** | Les réponses portent des **ids** et libellés déjà résolus (`spell_name`, `race_name`…) | Le moteur de règles reste serveur-side ; pas d'introspection compendium générique en v1 |
| **`ActionBudget`** | **Oui** (lecture) ; **Non** (écriture directe) | Sous-objet du combattant en combat actif | Consommé par les actions (`action`, `bonus_action`, …) ; pas de PATCH manuel du budget |

### 1.3 Identifiants stables exposés

| Identifiant | Portée | Stabilité contractuelle |
|---|---|---|
| `character_id` | Persistant, cross-session | Stable — clé SQLite courte (ex. affichée par `/perso-afficher`) |
| `combat_id` | Rencontre | Stable — entier SQL auto-incrémenté |
| `combatant_id` | Rencontre | Stable **dans** la rencontre — UUID tronqué (8 car.) assigné à l'ajout ; opaque pour le client |
| `spell_id`, `condition_id`, `effect_id` | Ruleset / catalogue moteur | Stable — alignés compendium et catalogues phase (`PHASE1_CONDITIONS`, sorts combat YAML) |
| `ability_id`, `skill` | Ruleset | Stable — vocabulaire SRD 2014 (`str`, `dex`, `perception`, …) |

**Alternative écartée** : exposer des ids numériques internes SQL pour les combattants — rejeté : le moteur ne les utilise pas ; seul `combatant_id` string est la clé du dict `combatants`.

**Alternative écartée** : masquer `effect_id` derrière des enums numériques — rejeté : casse la lisibilité debug, duplique le compendium, et empêche l'extension par sorts/conditions sans bump de table de correspondance.

### 1.4 Double source Character / Combatant — règle temporelle API

Alignement ADR-005 (non négociable par l'API) :

- **Pendant** `status ∈ {preparing, active}` : les PV et la CA lus pour le combat viennent du **combattant** overlay.
- **Après** `close_combat` : les PV persistés sur la **fiche** sont synchronisés ; les conditions et effets de rencontre **ne** sont **pas** propagés sur la fiche (encounter-scoped, ADR-005 §4).
- Un `GET /characters/{id}/sheet` pendant un combat actif reflète la fiche **pré-rencontre** (ou post-close), **pas** l'overlay — sauf décision contraire explicite [À TRANCHER — voir §2.4].

---

## 2. Modèle d'état et de session

### 2.1 Qui possède la session de combat

**Décision** : le **serveur** possède l'état ; le client le **référence** par `combat_id` (entier) dans les chemins de ressource.

Il n'y a **pas** de session HTTP (cookie, token de session combat). Chaque requête est authentifiée… — hors v1 (§6) — et identifie le combat par URL.

**Alternative écartée** : session opaque type `session_token` mappée en mémoire seule — rejetée : incompatible avec reprise après redémarrage serveur et avec le modèle SQLite déjà en place.

### 2.2 Cycle de vie — alignement moteur strict

L'API **reprennent exactement** les statuts `CombatStatus` :

```
preparing → active → ended
```

| Transition moteur | Sémantique API | Notes |
|---|---|---|
| `create_combat` | Création ressource combat | Statut initial `preparing` |
| `add_combatant` | Ajout participant (preparing only) | |
| `activate_combat` | Activation | Passe `active`, initiative, round 1 |
| Mutations en combat | Actions POST sous `/combats/{combat_id}/…` | Chaque mutation persistée (`_persist`) |
| `close_combat` | Clôture explicite ou conséquence d'`advance_turn` à 0 actif | Séquence ADR-005 § hook unique |
| `load_combat` | Rechargement **interne** serveur | Pas un endpoint client obligatoire en v1 ; utilisé pour réhydrater registre et concentration |

**Séquence `close_combat` (contrat de sémantique, ordre observé côté moteur)** — l'endpoint de clôture API doit déclencher cette séquence sans la réordonner :

1. Sync PV overlay → fiche (`character.hp_current`)
2. Réconciliation concentration overlay → fiche
3. Conditions / effets rencontre : discard fiche (archive blob autorisée)
4. `status=ended`, `ended_at`, persistance combat, `CombatEnded`

**Alternative écartée** : introduire un statut API intermédiaire (`paused`, `between_rounds`) — rejetée : créerait une seconde machine à états divergente du blob.

### 2.3 Persistance : reconstruction vs mémoire

**État observé dans le code** :

- **Source de vérité durable** : blob JSON `CombatState` + colonne `status` SQL (`SqliteCombatRepository`).
- **Cache process** : `CombatManager._effect_registries` — registre d'effets **en mémoire** par `combat_id`, reconstruit depuis `active_effects` du blob via `_sync_effect_registry_from_state` à chaque `load_combat` / `_persist`.
- **Conséquence redémarrage serveur** : aucune perte si SQLite intacte ; prochaine requête charge depuis la base et réhydrate le registre. Pas de sticky session requise.

**Décision API** : modèle **stateless HTTP + état serveur durable**. Le client n'envoie pas l'état combat ; il envoie des **commandes** idempotentes… — idempotence **non** garantie en v1 (§6).

**Alternative écartée** : le client POSTe le blob combat complet à chaque action — rejetée : race conditions, taille, duplication de la logique de validation.

### 2.4 Concurrence

**Décision (alignée `docs/API_LOCAL.md` et bot Discord)** : **dernier écrivain gagne** — pas de verrou optimiste, pas d'`ETag` en v1.

Deux requêtes concurrentes sur le même `combat_id` ou le même `character_id` peuvent se recouvrir ; l'ordre d'application est celui des commits SQLite.

**[À TRANCHER] — Concurrence combat**

| Option | Conséquence client |
|---|---|
| **A. Conserver last-writer-wins** (recommandé v1 banc de test) | Simple ; documenter l'interdiction d'accès parallèle |
| **B. `revision` entier sur combat + header `If-Match`** | 409 `STATE_CONFLICT` ; migration clients si ajout tardif |
| **C. File d'actions sérialisée par combat** | Contrat temps réel implicite ; complexité serveur |

### 2.5 Clés de regroupement `guild_id` / `channel_id`

Le moteur impose aujourd'hui l'unicité « un combat ouvert par `(guild_id, channel_id)` » (`OpenCombatExistsError`).

**[À TRANCHER] — Scope de création pour clients non-Discord**

| Option | Conséquence |
|---|---|
| **A. Conserver guild/channel obligatoires** | Le client HTTP fournit un couple scope arbitraire (ex. `api-local` / `session-uuid`) |
| **B. Assouplir le moteur** (hors contrat API seul) | Permettre plusieurs combats ouverts sans scope Discord — migration repository |
| **C. Scope implicite singleton global dev** | Un seul combat ouvert — limite les tests parallèles |

### 2.6 Lecture fiche pendant combat actif

**[À TRANCHER]**

| Option | Conséquence |
|---|---|
| **A. Sheet = fiche persistée uniquement** (alignement strict ADR-005) | Le client combat lit les PV via `GET /combats/{id}` |
| **B. Sheet enrichie overlay si combat actif** | Deux vérités fusionnées côté API — risque de confusion ; simplifie un client monolithique |

---

## 3. Format d'erreur

### 3.1 Structure unique (contrat)

Toute réponse d'erreur HTTP **4xx/5xx** métier ou validation utilise un **corps JSON objet** avec clé racine `error` :

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
| `code` | **Oui** | **Contrat** — code machine stable, `SCREAMING_SNAKE_CASE` |
| `message` | **Oui** | Hint humain ; français ; **non garanti** stable (texte libre) |
| `details` | Non | Objet JSON extensible (ex. `{"combat_id": 3, "status": "ended"}`) ; clés stables une fois documentées |

**Alternative écartée** : message seul dans `detail` string (FastAPI par défaut actuel) — rejetée pour le contrat cible : impossible d'internationaliser ou de brancher un client sur le texte ; changement de message = rupture implicite.

**Migration** : l'API personnage existante (`HTTPException(detail=str)`) devra adopter ce format — **breaking change** assumé pour unifier.

### 3.2 Correspondance familles d'erreurs → HTTP

| HTTP | Famille | Exemples `code` (illustratif, non exhaustif) |
|---|---|---|
| **404** | Ressource absente | `CHARACTER_NOT_FOUND`, `COMBAT_NOT_FOUND`, `COMBATANT_NOT_FOUND` |
| **409** | Règle métier / conflit d'état | `SPELL_CAST_REJECTED`, `REST_REJECTED`, `COMBAT_STATUS_INVALID`, `UNKNOWN_CONDITION`, `ACTION_BUDGET_EXHAUSTED`, `OPEN_COMBAT_EXISTS`, `INSUFFICIENT_COMBATANTS`, `NOT_COMBATANT_TURN`, `SPELL_ATTACK_TYPE_MISSING` |
| **422** | Corps de requête invalide | `VALIDATION_ERROR` (+ détails pydantic dans `details`) |
| **500** | Erreur inattendue | `INTERNAL_ERROR` — message générique côté client ; pas de fuite stack |

**Décision** : les erreurs métier typées du moteur (`SpellCastError`, `CombatStatusError`, `UnknownCombatConditionError`, …) mappent **toutes** en **409** sauf celles explicitement « not found » (404). Distinction alignée sur l'API actuelle (`docs/API_LOCAL.md`).

**Alternative écartée** : HTTP 400 pour toutes les erreurs métier — rejetée : mélange validation syntaxique et règles SRD ; les clients ne peuvent pas distinguer « JSON mal formé » de « sort refusé ».

### 3.3 Table de correspondance moteur → `code` (minimum contractuel)

Le mapping exact sera enrichi à l'implémentation ; les lignes ci-dessous **engagent** la stabilité du `code` une fois publié :

| Exception / cas moteur | `code` proposé |
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
| `require_spell_attack_type` / `SpellCastError` attaque | `SPELL_ATTACK_TYPE_MISSING` |

---

## 4. Conventions de nommage et de versionnement

### 4.1 Chemins de ressources

**Décision** :

- Ressources au **pluriel**, segments en **snake_case** : `/characters`, `/combats`.
- Identifiants dans le chemin : `{character_id}`, `{combat_id}` (integer).
- Actions sous ressource : verbe en **kebab-case** post fixé ou sous-chemin action — ex. `/combats/{combat_id}/attack-roll`, `/combats/{combat_id}/close`, `/characters/{id}/long-rest` (cohérent avec l'existant).
- Pas de verbes à la racine sauf diagnostic dev explicite (`/debug/…` hors contrat prod).

**Alternative écartée** : RPC style `/executeAttack` — rejetée : mélange modèle ressource et procédure ; complique la versionnement par ressource.

### 4.2 Champs JSON

**Décision** : **snake_case** partout ; aligné sur `output_serializers.py` et le compendium.

Vocabulaire SRD / moteur **conservé** tel quel :

- `ability_id`, `spell_id`, `condition_id`, `effect_id`, `source_id`, `target_id`
- `hp_current`, `hp_max`, `ac`, `round_number`, `initiative_order`
- Modes de jet : `normal`, `avantage`, `desavantage` (libellés moteur français — **décision coûteuse** : changer casserait les clients ; alternative anglaise écartée pour cohérence Discord/moteur)

Clés dict niveau d'emplacement : **string** (`"1"`, `"2"`) — convention DTO existante `_slots_to_dict`.

### 4.3 Versionnement API

**[À TRANCHER]**

| Option | Avantages | Inconvénients |
|---|---|---|
| **A. Préfixe `/v1/`** | Clair, routable, standard | Toutes les routes actuelles `/characters/…` migrent |
| **B. Pas de version URL v1** (banc local, `FastAPI.version="0.1.0"`) | Cohérent avec l'API actuelle minimale | Toute rupture future est implicite |
| **C. Header `Accept-Version: 1`** | URLs stables | Clients caches/proxies ignorent souvent ; moins visible |

**Recommandation rédactionnelle** : si l'objectif reste un **banc de test local** à court terme, **B** avec engagement de passer à **A** avant tout client externe — à valider mainteneur.

---

## 5. Périmètre du premier lot implémentable

Objectif : **aller-retour bout-en-bout démontrable** en une session — valider le modèle ressource/combat/erreur, pas couvrir le moteur.

### 5.1 Intention

Permettre à un client HTTP de :

1. Lire une fiche personnage existante (déjà livré).
2. Ouvrir une rencontre avec des personnages connus.
3. Activer la rencontre.
4. Exécuter **une** action de combat qui produit un jet d20 résolu (attaque d'arme avec contexte de portée).
5. Lire l'état combat mis à jour (PV, effets, tour).
6. Clore la rencontre et vérifier la sync PV fiche.

### 5.2 Ressources et intentions (sans schémas)

| Intention | Ressource / action | Repose sur |
|---|---|---|
| Fiche personnage | `GET /characters/{character_id}/sheet` | Existant |
| Créer rencontre | `POST /combats` | `create_combat` + `add_combatant` |
| Lire rencontre | `GET /combats/{combat_id}` | Blob + DTO combat (à créer) |
| Activer | `POST /combats/{combat_id}/activate` | `activate_combat` |
| Jet d'attaque | `POST /combats/{combat_id}/attack-roll` | `resolve_attack_roll` — corps minimal : `attacker_id`, `target_id`, contexte portée |
| Clore | `POST /combats/{combat_id}/close` | `close_combat` |

**Hors premier lot implémentable** (même si le moteur le supporte) : sorts en combat, conditions, avancement de tour, dégâts, repos, debug events, création personnage, montée de niveau.

**Alternative écartée** : premier lot = uniquement jets hors combat (`/roll`) — rejetée : ne valide pas la frontière Character/Combatant ni la session combat, pourtant structurante.

---

## 6. Hors périmètre explicite (v1 contrat)

| Exclusion | Raison |
|---|---|
| **Authentification** | Banc local ; ajout ultérieur ne doit pas imposer un modèle de token dans les payloads v1 |
| **Autorisation** (ownership `character_id`) | Même justification ; 404 suffit masquage en dev |
| **Rate limiting** | Infra, pas contrat métier |
| **Pagination** | Volume prévu faible (combats dev, fiches unitaires) |
| **WebSocket / temps réel** | Événements via polling ou lecture post-action ; SSE/WS = contrat transport distinct |
| **OpenAPI générée comme contrat** | Peut exister en aide ; le contrat normatif reste ce document + codes d'erreur stables |
| **CORS** | Déploiement ; le client statique actuel est same-origin |
| **Déploiement / multi-instance** | Last-writer-wins SQLite local ; scaling = autre ADR |
| **Idempotency-Key** | Reporté ; les POST combat mutent l'état |
| **Webhooks** | Pas de push événementiel client |
| **Introspection compendium** | Les ids passent par le moteur ; pas de `GET /spells` général en v1 |
| **Création / édition personnage** | Périmètre bot / autre lot |
| **Couverture complète action economy** | Avancement tour, actions bonus, etc. — extensions après validation du noyau |

---

## 7. Référence — ce que Discord expose déjà

Les handlers Discord **ne sont pas** le contrat API, mais indiquent ce que l'UI joueur consomme aujourd'hui :

- Fiche / actions personnage (sorts, repos) — partiellement recouvert par l'API HTTP actuelle.
- `/roll` avec flags combat (`CombatRollFlags` : `ranged_weapon`, `rage_active`, `reckless`, …) — **analogue** du sous-ensemble « contexte de jet » attendu côté HTTP pour les attaques.
- Combat Discord : sous-ensemble des opérations `CombatManager` ; pas d'exposition directe du registre ni du blob.

L'API HTTP vise **strictement plus** que Discord (état combat structuré) sans reprendre le rendu embed.

---

## 8. Incohérences document / code (signalées, non corrigées)

| Point | Document | Code observé (2026-08-07) |
|---|---|---|
| Conditions et `ActiveEffect` | ADR-006 §2 « frightened/poisoned hors scope — overlay blob-only » | Conditions phase 1 migrées vers registre `ActiveEffect(manual)` ; blob `conditions[]` legacy hydraté à `load_combat` |
| Collecteur conditions | ADR-004 §538, §748 : `rules/combat/conditions/collect.py` | Fichier **supprimé** ; collecte dans `rules/effects/collect.py` (attaquant / défenseur) |
| Format d'erreur API | `docs/API_LOCAL.md` : `detail` string | Contrat cible §3 : objet `error` structuré — **migration à prévoir** |
| Atomicité `close_combat` | ADR-005 § atomicité : sync fiches puis combat `ended` recommandé | Implémenté ; écritures multi-connexion SQLite **non transactionnelles** — limite toujours ouverte |
| API combat | Ce contrat | **Aucun** endpoint combat HTTP — `interfaces/api/` = personnage uniquement |
| Tests de référence | AGENTS.md baseline historique 645 | **866** tests mesurés post-lot prone |

---

## 9. Synthèse des décisions à figer avant implémentation

| # | Décision | Statut |
|---|---|---|
| 1 | Ressources : Character, Combat (avec Combatant + ActiveEffect snapshot) | **Tranché** |
| 2 | Registre, collecteurs, D20RollRequest complet : internes | **Tranché** |
| 3 | Session = `combat_id` + SQLite ; pas de sticky session | **Tranché** |
| 4 | Cycle de vie = `preparing` / `active` / `ended` moteur | **Tranché** |
| 5 | Concurrence last-writer-wins v1 | **Tranché** (option B revision [À TRANCHER]) |
| 6 | Format erreur `{ error: { code, message, details? } }` | **Tranché** |
| 7 | Métier → 409, not found → 404 | **Tranché** |
| 8 | snake_case, ids SRD stables exposés | **Tranché** |
| 9 | Versionnement URL | **[À TRANCHER]** |
| 10 | Scope guild/channel clients HTTP | **[À TRANCHER]** |
| 11 | Sheet pendant combat actif | **[À TRANCHER]** |

---

## Références

- `docs/adr/ADR-005-transition-fin-rencontre.md` — sync-on-close, conditions encounter-scoped
- `docs/adr/ADR-006-modele-effets-actifs.md` — ActiveEffect, registre, horloge rounds
- `docs/API_LOCAL.md` — API personnage actuelle (limites concurrence, codes HTTP de facto)
- `jdr_engine/game/combat_manager.py` — cycle de vie, `_effect_registries`, `close_combat`
- `jdr_engine/rules/effects/collect.py` — collecteurs attaquant/défenseur
- `jdr_engine/application/dto/output_serializers.py` — principes DTO (données, pas texte formaté)
- `interfaces/api/app.py` — surface HTTP existante
