# ADR-004 — Modèle de combat

| Attribut | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-08-03 |
| **Décideurs** | Lead Architect, Product Owner |
| **Contexte** | ÉTAPE 4 — Système de combat (API moteur pure, ROADMAP C0–C7) |

---

## Contexte

Le projet **JDR Engine** dispose d'un moteur de règles D&D 5e (SRD 2014) avec personnages persistés en SQLite, incantation, repos et affichage de fiche — mais **aucun module de combat** (`jdr_engine/game/` et `jdr_engine/rules/combat/` sont des placeholders). Les sorts offensifs calculent des dégâts sans les appliquer ; la concentration est un marqueur persisté dans `choices.spellcasting` sans save CON ni effets mécaniques de buff.

Avant d'implémenter l'ÉTAPE 4, sept arbitrages de conception ont été tranchés lors d'une session de préparation (inventaire : `docs/COMBAT_PREP_MODELE.md`). Ce document les formalise. Il ne rouvre pas le débat : il fixe le modèle sur lequel s'appuieront les lots C0–C7 et le lot B4 (effets de sorts).

**Contraintes héritées** (VISION.md §5, ADR-003) :

- Le combat est une **API moteur pure** — fonctions déterministes + événements publiés, sans rendu Discord ni Web.
- Le **Rule Engine** calcule ; le **Game Engine** orchestre (tours, cibles, commandes).
- `Character` reste l'entité persistée du personnage-joueur.

---

## Décision 1 — Points de vie : mutation directe de `Character.hp_current`

### Décision

Les dégâts et soins en combat **modifient directement** `Character.hp_current`. Il n'existe pas de champ `hp_current_combat` ni d'overlay de PV propre à la rencontre sur `Combatant`.

### Justification

Le code actuel mute déjà `hp_current` en place : `_apply_healing()` dans `cast.py`, repos court et long, montée de niveau, endurance implacable. L'API locale persiste le personnage après chaque action — la mutation directe est le **contrat implicite** déjà en vigueur.

En règles 5e, les PV perdus ne se régénèrent qu'au repos, pas à la fin d'une rencontre. Un overlay créerait une double source de vérité sur le champ le plus fréquemment modifié du modèle, avec une synchronisation fin de combat à définir et à tester sans gain mécanique SRD.

### Alternatives envisagées

| Alternative | Pour | Contre | Verdict |
|---|---|---|---|
| **Overlay PV sur `Combatant`** | Snapshot début de rencontre ; abandon sans toucher la fiche | Double source PV ; sync explicite vers `Character` ; incohérent avec persistance API actuelle | **Rejetée** |
| **Copie PV au début, commit en fin de rencontre** | « Reset » implicite si on oublie de commit | Contredit le SRD (PV perdus persistent) ; perte d'état si crash mid-combat | **Rejetée** |
| **Mutation directe de `Character.hp_current`** | Aligné code, persistance, SRD | Pas de distinction session/combat (non requis par les règles) | **Retenue** |

### Conséquences

- `rules/combat/damage.py` (lot C3a) opère sur un `Character` ou sur des valeurs dérivées de sa fiche, puis **écrit** `hp_current`.
- `CombatState` / `Combatant` ne dupliquent pas les PV ; ils référencent `character_id` et s'appuient sur `build_character_sheet()` pour CA et modificateurs de base.
- C7 (auto-save) persiste le `Character` après événements `DamageDealt` / `HealingApplied` — cohérent avec le flux API existant.
- Les tests assertent `character.hp_current` après résolution, sans couche de merge overlay.

---

## Décision 2 — Concentration : source de vérité unique dans `choices.spellcasting.concentration`

### Décision

La concentration active est **uniquement** stockée dans `choices.spellcasting.concentration` (`{spell_id, spell_name}`). Deux fonctions partagées encapsulent toute lecture/écriture :

- `set_concentration(character, spell_id, spell_name)` — pose ou remplace ;
- `clear_concentration(character)` — efface.

Ces fonctions sont implémentées dans **`jdr_engine/rules/spellcasting/concentration.py`**, module dédié. Elles sont appelées par **`cast.py`** (incantation hors combat) **et** par le moteur de combat (rupture save CON, etc.). `ActiveEffect` (runtime combat) **expose** la concentration comme **vue dérivée** de ce stockage — jamais comme source parallèle.

### Justification

Treize sorts, l'API FastAPI, l'adaptateur Discord et la logique de repos lisent déjà `choices.spellcasting.concentration`. Un modèle dual (`ActiveEffect` + `choices`) avec synchronisation réintroduirait la dette de double source que la décision 1 élimine pour les PV. Une migration complète vers `ActiveEffect` comme seule source serait un breaking change sans bénéfice immédiat.

Le point d'entrée unique réside dans **`rules/spellcasting/concentration.py`** — et non dans `state.py`, qui agrège déjà des responsabilités hétérogènes (emplacements, grimoire, préparés). Y placer ce wrapper nuirait à sa repérabilité, ce qui contredirait l'intention même de la décision.

### Alternatives envisagées

| Alternative | Pour | Contre | Verdict |
|---|---|---|---|
| **Dual : `ActiveEffect` runtime + sync vers `choices`** | Séparation combat / persistance | Synchronisation, risque de divergence, deux chemins de rupture | **Rejetée** |
| **Migration totale vers `ActiveEffect`** | Modèle unifié long terme | Breaking change API/Discord/repos ; refactor large avant MVP | **Rejetée à ce stade** |
| **Wrapper unique sur `choices` + vue dérivée** | Compatibilité ; un seul point d'écriture | `ActiveEffect` moins autonome pour la concentration | **Retenue** |

### Conséquences

- Refactor léger de `cast.py` : `_set_concentration()` délègue à `set_concentration()` exportée depuis `rules/spellcasting/concentration.py` ; `clear_concentration()` y est centralisé (migration depuis `state.py`).
- C5 (save CON sur dégâts) appelle `clear_concentration()` après rupture — même chemin que repos long/court.
- Le registre B4 et `collect_roll_effects()` liront la concentration via ce point unique pour brancher les modificateurs (`hunters_mark`, puis `bless`).
- Tests existants (`test_cast_concentration.py`) restent valides ; ajout de tests combat sur les mêmes fonctions.

---

## Décision 3 — Lot C1 : `Combatant` limité aux personnages-joueurs

### Décision

`Combatant` est introduit dès le lot **C1**, mais se construit **exclusivement** à partir d'un `character_id` existant, via `build_character_sheet()`. Aucune injection de statistiques arbitraires (CA, PV max, modificateurs saisis à la main).

### Justification

La base SQLite contient déjà des personnages jouables ; le compendium **monstres est vide**. Construire un chemin « stats injectées » avant le besoin PNJ ajoute de la surface API sans cas de test réel. La contrainte de construction depuis `character_id` laisse la porte ouverte à une généralisation ultérieure dont la forme dépendra du compendium monstres.

### Alternatives envisagées

| Alternative | Pour | Contre | Verdict |
|---|---|---|---|
| **`Combatant` statique (CA/PV injectés)** | PNJ sans fiche complète dès C1 | Compendium monstres absent ; risque de contournement du principe d'intégrité des stats | **Rejetée pour C1** |
| **Reporter `Combatant` après C3** | Moins de modèle upfront | C1 ROADMAP exige participants + état rencontre | **Rejetée** |
| **`Combatant` PJ-only via `character_id`** | Tests PJ vs PJ ; aligné persistance | PNJ reportés | **Retenue** |

### Conséquences

- C1 : `CombatManager.start(combat_id, character_ids: list[str])` charge les `Character` depuis le repository.
- MVP combat = **PJ contre PJ** (ou un seul PJ pour tests unitaires).
- Extension PNJ/monstre = lot ultérieur, probablement via compendium + entité distincte ou constructeur dédié **sans** modifier le contrat C1 des PJ.

---

## Décision 4 — Conditions : énumération en dur pour la phase 1

### Décision

Les conditions SRD de la phase 1 (p.ex. `frightened`, `poisoned`, `prone`) sont définies dans une **énumération ou un registre en dur**, isolé dans **un module Python dédié** (p.ex. `jdr_engine/domain/effects/conditions_phase1.py` ou `jdr_engine/rules/combat/conditions/catalog.py`).

**Pas** de loader compendium, **pas** de manifest, **pas** de schéma YAML avant le lot **C6**.

### Justification

Trois conditions ne justifient pas l'infrastructure compendium (manifest, validation, loader, entrées YAML). L'énumération centralisée garantit une **migration localisée** vers `compendium/dnd5e/entries/conditions/` lorsque le volume le justifiera.

### Dette technique assumée

| Dette | Résorption |
|---|---|
| Conditions hors compendium | **Lot C6** — création de `entries/conditions/` et remplacement du module dédié par le loader existant |
| Impact jets codé en dur dans `resolve.py` | Migré avec les entrées compendium |

**Échéance** : liée au lot C6 ; pas de date fixe au-delà de la ROADMAP.

### Alternatives envisagées

| Alternative | Pour | Contre | Verdict |
|---|---|---|---|
| **Compendium conditions dès C1** | Data-driven dès le départ | Coût manifest + schéma + 3 YAML pour un MVP | **Rejetée phase 1** |
| **Enum dispersée dans le code combat** | Rapide | Migration C6 = chasse aux références | **Rejetée** |
| **Module unique dédié, enum phase 1** | MVP rapide ; migration localisée | Dette explicite jusqu'à C6 | **Retenue** |

### Conséquences

- C6 implémente apply/remove + hooks jets pour 2–3 conditions depuis le module dédié.
- Aucun travail compendium conditions avant C6.
- La documentation ARCHITECTURE devra mentionner la dette jusqu'à migration.

---

## Décision 5 — `feature_state` : migration reportée

### Décision

Rage, ki, second wind, endurance implacable et les autres états de **`choices.feature_state`** **conservent** leur mécanisme actuel (`class_features/common.py`, injection partielle dans `roll_d20_for_character`). **Aucune migration** vers `ActiveEffect` pendant la construction de la boucle de combat (C0–C7).

### Justification

Deux refactors simultanés (combat + unification effets classe) multiplient le risque et la surface de régression sur douze classes déjà jouables. Le mécanisme existant **fonctionne** et **ne bloque pas** le MVP combat (initiative, attaque, dégâts, concentration save).

### Dette technique assumée

| Dette | Résorption |
|---|---|
| `feature_state` ad hoc vs `ActiveEffect` unifié | **Sans échéance fixe** — lot post-MVP combat, après validation du modèle d'effets via B4/C6 |
| Rage/reckless hors `Combatant.flags` tour | Accepté ; enrichissement progressif possible sans refactor global |

### Alternatives envisagées

| Alternative | Pour | Contre | Verdict |
|---|---|---|---|
| **Migrer `feature_state` → `ActiveEffect` en C1** | Modèle unique dès le départ | Refactor 12 classes + tests ; bloque la boucle combat | **Rejetée** |
| **Dual temporaire avec sync** | Pont vers ActiveEffect | Complexité sync ; même problème que concentration dual | **Rejetée** |
| **Reporter la migration** | Focus C0–C7 ; code éprouvé | Deux systèmes d'effets coexistants temporairement | **Retenue** |

### Conséquences

- `collect_roll_effects()` et `enrich_roll_request()` restent le chemin rage/reckless/expertise en combat.
- `ActiveEffect` phase 1 sert surtout aux **effets de sorts** (B4) et **conditions** (C6), pas aux features de classe.
- Un futur ADR ou RFC pourra trancher la migration classe par classe.

---

## Décision 6 — Persistance de l'état de combat : SQLite

### Décision

L'état de rencontre est persisté dans **SQLite**, table **`combats`**, dans le fichier **`data/bot.db`** — le **même fichier** que la table `personnages`. L'état est sérialisé en **JSON** dans une colonne (snapshot `CombatState` + métadonnées). **Pas** de répertoire `data/combats/` en fichiers plats.

### Justification

Une seule infrastructure de persistance à maintenir, sauvegarder et migrer. L'inspection manuelle reste possible via `sqlite3` en ligne de commande ; le gain de lisibilité des fichiers plats ne compense pas un second mécanisme de persistance.

Centraliser `personnages` et `combats` dans **`data/bot.db`** évite deux fichiers SQLite — donc deux connexions, deux chaînes de migration et deux périmètres de sauvegarde — précisément la dispersion que la décision écarte en rejetant les fichiers plats.

### Alternatives envisagées

| Alternative | Pour | Contre | Verdict |
|---|---|---|---|
| **Fichiers `data/combats/*.json`** | Diff git-friendly ; debug visuel | Deux systèmes ; concurrence ; backup séparé | **Rejetée** |
| **État combat uniquement en mémoire** | Simple | Perte crash ; incompatible C7 auto-save | **Rejetée** |
| **Table SQLite `combats` + JSON dans `data/bot.db`** | Cohérent avec personnages ; une connexion ; migrations centralisées | JSON moins lisible que fichiers (mitigé par sqlite3 CLI) | **Retenue** |
| **Base SQLite séparée pour les combats** | Isolation des domaines | Deux connexions, deux migrations, deux sauvegardes | **Rejetée** |

### Conséquences

- **Lot C1 (implémenté)** : `combat_repository.py` + table `combats` dans `database.py` (schéma SQL v2).
- Handler EventBus `CombatAutoSaveHandler` — **lot C7** (non implémenté).
- `ARCHITECTURE_TARGET.md` (snapshots fichiers) est **supplanté** par cette décision pour l'implémentation.

### Décision 6bis — Granularité et schéma SQL (lot C1, 2026-08-03)

| Élément | Choix |
|---|---|
| **Stockage** | Un seul blob JSON (`state_json`) — pas de tables liées participants |
| **Fichier** | `data/bot.db`, table `combats` |
| **Clé primaire** | `id INTEGER PRIMARY KEY AUTOINCREMENT` ; `combat_id` métier = `str(id)` |
| **Rattachement** | Colonnes `guild_id`, `channel_id` |
| **Unicité** | **Un combat ouvert par salon** (`preparing` ou `active`) — index unique partiel SQLite `idx_combats_open_channel WHERE status IN ('preparing', 'active')` + colonne SQL `status` (`preparing` \| `active` \| `ended`) |
| **Statut** | **Colonne SQL seule** — absent du blob JSON (correctif C1a) ; `CombatState.status` reconstruit à la lecture depuis la colonne |
| **Version blob** | Champ entier `schema_version` dans le JSON (`COMBAT_STATE_VERSION = 1`), distinct du schéma SQL (`DB_SCHEMA_VERSION = 3` depuis C2) ; lecture échoue explicitement si version inconnue |
| **Combats terminés** | Restent en base (`status = ended`) ; n'empêchent pas un nouveau combat actif sur le même salon |
| **Blob legacy C1** | Un champ `status` surnuméraire dans un blob v1 existant est **ignoré** à la lecture (pas d'erreur) |

**Justification blob unique** : l'état est toujours lu/écrit en intégralité ; pas de requête analytique cross-combat sur le contenu — cohérent ADR-004.

**Justification statut SQL uniquement** : la colonne est requise par l'index unique partiel ; la dupliquer dans le blob créait deux sources synchronisées à la main — une divergence aurait corrompu silencieusement la contrainte d'unicité (correctif C1a).

**Justification index partiel** : SQLite supporte `CREATE UNIQUE INDEX … WHERE status IN ('preparing', 'active')` ; un salon ne peut pas héberger deux combats ouverts simultanément (deux en préparation, ou préparation + actif).

**Migration SQL v2 → v3 (lot C2)** : recréation de la table `combats` pour étendre la contrainte `CHECK` à `preparing` ; remplacement de `idx_combats_active_channel` par `idx_combats_open_channel`. Les lignes `active` / `ended` existantes sont copiées telles quelles. Déclenchée par `ensure_combats_schema()` si la table ne contient pas encore `preparing` dans sa définition.

### Décision 6ter — Clôture idempotente (lot C1a, 2026-08-03)

`close_combat` sur un combat déjà `ended` **retourne l'état** sans republier `CombatEnded`.

**Justification** : une republication ferait rejouer les effets de fin de combat aux abonnés — risque aggravé en **C6** lorsque les effets en cascade existeront.

---

## Décision 8 — Initiative et cycle de tours (lot C2, 2026-08-03)

### Statut `preparing`

Un combat est **créé en `preparing`** : les combattants peuvent être ajoutés, l'initiative n'est pas établie, aucun tour n'existe (`round_number = 0`, `initiative_order` vide). Le passage en **`active`** est explicite (`activate_combat`) et déclenche le calcul de l'initiative. La validation d'un combat jouable — **au moins deux combattants actifs** — s'applique à l'activation, pas à la création.

### Ordre d'initiative figé

L'ordre est calculé **une fois** à l'activation et stocké dans le blob comme séquence ordonnée d'identifiants de combattants (`initiative_order`). Il **n'est pas recalculé** à chaque round. Les totaux de jet sont persistés sur chaque `Combatant.initiative_total`.

### Départage des égalités

À initiative totale égale, départage **déterministe** :

1. total décroissant ;
2. à égalité, `combatant_id` **croissant** (ordre lexicographique).

Implémenté dans `jdr_engine/rules/combat/initiative.py` (`sort_initiative_order`).

### Position courante

Le tour courant est un **`turn_index`** dans `initiative_order`, accompagné d'un **`round_number`**. L'avancement incrémente l'index ; le passage au round suivant se produit lorsque l'index atteint la fin de la séquence (retour à 0, `round_number += 1`).

### Retrait d'un combattant

Un combattant retiré est marqué **`is_active = False`** ; il **reste** dans `initiative_order` et son tour est **ignoré** à l'avancement.

### Événements publiés (C2)

| Événement | Moment |
|---|---|
| `CombatStarted` | Création (`preparing`) |
| `InitiativeRolled` | Activation |
| `TurnStarted` | Activation (premier tour) et chaque `advance_turn` |
| `TurnEnded` | Avant chaque avancement de tour |
| `RoundStarted` | Lorsque `round_number` s'incrémente |

Tous héritent directement de `DomainEvent` avec `kw_only=True` si champs obligatoires (ADR-003).

### Ambiguïtés laissées ouvertes (C2)

| Point | Traitement |
|---|---|
| **Fin de combat automatique** lorsqu'il ne reste qu'un ou zéro combattant actif | **Non tranché** — `advance_turn` lève `NoActiveCombatantsError` ; clôture explicite via `close_combat` |
| **Réactivation d'un combattant retiré** | **Non tranché** — hors périmètre C2 |
| **Initiative avec avantage/désavantage ou jets groupés** | **Non tranché** — jet simple 1d20 + mod DEX (SRD par défaut) |

---

## Décision 9 — Attaque et dégâts (lot C3a, 2026-08-03)

### PV en overlay combat

Les PV (`hp_current`, `hp_max`) et la **CA** (`ac`) vivent sur **`Combatant`** dans le blob JSON — **pas** sur `Character` pendant la rencontre. Initialisés depuis `build_character_sheet()` à l'ajout du combattant ; seuls les PV courants mutent lors des dégâts.

**Complète la décision 1** pour la durée d'une rencontre : la mutation directe de `Character.hp_current` reste le contrat hors combat (sorts, repos, API). La **synchronisation fiche ← overlay** en fin de combat est une décision **distincte** — non implémentée en C3a.

### Séparation jet d'attaque / application des dégâts

| Étape | Méthode | Événement |
|---|---|---|
| Jet vs CA | `resolve_attack_roll` | `AttackRollResolved` |
| Dégâts | `apply_damage` | `DamageDealt` |

Le toucher ne modifie pas les PV ; les dégâts sont réutilisables hors chemin d'attaque (sorts, chutes — lots ultérieurs).

### Moteur de jets existant

Le jet d'attaque consomme **`roll_d20_for_character`** → **`roll_d20`** (`jdr_engine/dice/d20.py`), y compris avantage/désavantage via `D20RollRequest.base_mode` et effets Compendium. **Aucune** réimplémentation du d20 dans le module combat.

### Critique et échec automatique

- **Nat 1** : échec automatique (`automatic_miss`), sans comparer à la CA.
- **Nat 20** : toucher automatique (`critical`), sans comparer à la CA.
- **Critique dégâts** : double le **nombre de dés** de la notation, **pas** le modificateur fixe (`1d8+3` → `2d8+3`). Implémenté dans `rules/combat/damage.py` (`roll_damage`).

### Économie d'actions

**Lot C4** — budget par tour avec réinitialisation à `TurnStarted` ; voir décision 11.

### Ambiguïtés laissées ouvertes (C3a)

| Point | Traitement |
|---|---|
| **Construction automatique du `D20RollRequest`** (arme, portée, maîtrise) | **Non tranché** — l'appelant fournit la requête pour les attaques d'arme ; les attaques de sort construisent la requête via `build_spell_attack_request` (C3b) |
| **Résistances / immunités** | **Non tranché** — extension future de `apply_damage` |

### Décision acquise — dégâts sans toucher préalable (C3b, 2026-08-03)

`apply_damage` **peut être appelé sans jet d'attaque préalable** — cohérence métier à la charge de l'appelant. Cas d'usage : sorts à sauvegarde (dégâts calculés puis appliqués via `damage_amount`), effets futurs hors attaque.

### Dette groupée — fin de combat (ensemble à traiter d'un bloc)

Les points suivants **ne sont pas tranchés individuellement** ; ils seront résolus **ensemble** dans un lot dédié :

| Point | Origine |
|---|---|
| **`advance_turn` avec ≤1 combattant actif** | Ambiguïté C2 |
| **Mort à 0 PV** (inconscient, retrait auto) | Ambiguïté C3a |
| **Synchronisation overlay combat → fiche `Character`** | ADR décision 1 / C3a |
| **Double source concentration** (overlay + fiche) | Ambiguïté C3b |

### Dette explicite — buffs inertes (C3b → B4)

Les champs overlay **`blessed`** et **`hunters_mark_caster_id`** posent un **état inerte** en C3b — aucun effet mécanique sur les jets. Leur activation relève du lot **B4** (`hunters_mark` puis `bless`).

---

## Décision 10 — Sorts en combat (lot C3b, 2026-08-03)

### Réutilisation C3a

| Mécanique | Chemin |
|---|---|
| Attaque de sort vs CA | `build_spell_attack_request` → `roll_d20_for_character` → **`resolve_attack_hit`** (C3a) |
| Dégâts | **`roll_damage`** + **`apply_damage`** / `damage_amount` (C3a) |
| Moitié sur save | **`damage_after_save`** sur le **total** des dés — pas sur chaque dé individuellement |

### DD de sauvegarde

Calculé via **`get_spellcasting_stats`** / `spell_save_dc` — **8 + maîtrise + mod incantation**. Non fourni par l'appelant.

### Concentration

Sorts à concentration (`hunters_mark`, `bless`) : **`set_concentration`** (module `concentration.py` depuis C5) + overlay sur le combattant lanceur (`concentration_spell_id`).

### Sorts implémentés (C3b)

| Sort | Type | Overlay combat |
|---|---|---|
| `fire_bolt` | Attaque de sort | — |
| `burning_hands` | Sauvegarde DEX | — |
| `hunters_mark` | Buff + concentration | `hunters_mark_caster_id` sur cible |
| `bless` | Buff + concentration | `blessed=True` sur cibles (max 3) — **état inerte jusqu'à B4** |
| `hunters_mark` | Buff + concentration | `hunters_mark_caster_id` sur cible — **état inerte jusqu'à B4** |

Le **+1d4 mécanique** de `bless` et le **+1d6** de `hunters_mark` sur les attaques relèvent de **B4** — seul l'état de buff est posé en C3b (voir dette explicite buffs inertes).

### Événements (C3b)

| Événement | Moment |
|---|---|
| `SpellCast` | Lancement (tous types) |
| `AttackRollResolved` | Attaque de sort (réutilisé C3a) |
| `SavingThrowResolved` | Jet de sauvegarde cible |
| `DamageDealt` | Application des dégâts (réutilisé C3a) |

### Hors périmètre C3b

- Emplacements de sorts (resync ROADMAP post-C4)
- Rupture de concentration sur dégâts (**C5** ✅ décision 12)
- Application mécanique des buffs (**B4** / **C6**)

### Ambiguïtés laissées ouvertes (C3b)

| Point | Traitement |
|---|---|
| **AoE multi-cibles** (`burning_hands` cône) | C3b : une cible par appel ; zone complète non modélisée |
| **Remplacement de marque** (`hunters_mark` sur nouvelle cible) | Non tranché |

---

## Décision 11 — Économie d'actions (lot C4, 2026-08-04)

### Budget par tour

Chaque combattant possède un **`ActionBudget`** dans l'overlay (`action_budget` sur `Combatant`) :

| Composante | Quantité par tour |
|---|---|
| Action | 1 |
| Action bonus | 1 |
| Réaction | 1 |
| Déplacement | 1 |

### Réinitialisation à `TurnStarted`

Au **`TurnStarted`** du combattant concerné uniquement, budget remis à **`fresh_action_budget()`** — pas de mécanisme parallèle.

### Réaction — mécanisme distinct

- Consommable **hors tour propre** via `consume_reaction` (lève `NotCombatantTurnError` sur son propre tour).
- **Non réinitialisée** au `TurnStarted` des autres combattants.
- **Réinitialisée** au `TurnStarted` du réactant (inclus dans `fresh_action_budget()`).

### Refus et événements

- Budget épuisé → **`ActionBudgetExhaustedError`** (pas d'événement).
- Hors tour → **`NotCombatantTurnError`**.
- Consommation effective → **`ActionConsumed`** (`action_kind` : `action` \| `bonus_action` \| `reaction` \| `movement`).

### Rattachement actions existantes

| Méthode | Budget consommé |
|---|---|
| `resolve_attack_roll` | `action` |
| `cast_spell_attack` | `action` (via `resolve_attack_roll`) |
| `cast_spell_save` | `action` |
| `cast_bless` | `action` |
| `cast_hunters_mark` | `bonus_action` |
| `apply_damage` | — (aucun) |

### Hors périmètre C4

- Emplacements de sorts (cycle repos long, fiche)
- Attaques multiples (Extra Attack), actions gratuites, interactions d'objet
- Privation d'action par conditions (**C6**)

### Dette explicite — déplacement (C4)

Le composant **`movement`** de `ActionBudget` pose un **état inerte** en C4 — le budget est réinitialisé à `TurnStarted` et exposé via l'API (`consume_movement`), mais **aucune action de combat ne l'invoque**. Une consommation mécanique exigerait un modèle de déplacement (distance, vitesse, cases) absent du MVP combat actuel. **Aucun lot de rattachement identifié** à ce stade — même pattern que les buffs inertes C3b (§ dette explicite buffs), sans cible B4.

### Ambiguïtés laissées ouvertes (C4)

| Point | Traitement |
|---|---|
| **Réaction sur son propre tour** (certaines features) | Non tranché — refus par défaut |
| **Action bonus / action interchangeables** (certaines features) | Non tranché |

---

## Décision 12 — Concentration en combat (lot C5, 2026-08-04)

### Module unique

`set_concentration` / `clear_concentration` / `get_active_concentration` vivent dans **`jdr_engine/rules/spellcasting/concentration.py`**. `cast.py`, les repos et le moteur de combat y délèguent — refactor reporté depuis C3b (§ décision 2).

### Rupture sur dégâts

Après **`apply_damage`**, si la cible concentre un sort et que les dégâts effectivement appliqués sont **> 0** :

1. DD = **`max(10, dégâts ÷ 2)`** (division entière) ;
2. jet de sauvegarde **CON** de la cible ;
3. échec → **`clear_concentration()`** sur la fiche + nettoyage overlay lanceur + événement **`ConcentrationBroken`**.

Le hook s'exécute **après** la publication de **`DamageDealt`**.

### Détection de concentration

Overlay **`concentration_spell_id`** prioritaire ; repli sur **`choices.spellcasting.concentration`** si l'overlay est absent (double source non unifiée — dette fin de combat).

### Nettoyage local

C5 efface overlay et fiche **à la rupture uniquement** — pas de résolution du groupe « fin de combat » (sync globale overlay ↔ fiche).

### Événement

| Événement | Moment |
|---|---|
| `ConcentrationBroken` | Échec du save CON après dégâts |

Aucun événement publié si le save réussit ou si la cible ne concentre pas.

### Hors périmètre C5

| Point | Traitement |
|---|---|
| **Expiration de durée** | **Hors C5** — horloge combat absente (dette B4). La ROADMAP mentionnait l'expiration en C5 ; **ADR-004 prime** : poser une durée sans décompte reproduirait le piège du budget de déplacement (état jamais consommé). |
| **Rupture volontaire** | Non actée — hors C5 |
| **Remplacement par un autre sort concentré** | Déjà couvert par `set_concentration` (Lot 1 / C3b) |
| **Conditions SRD brisant la concentration** | **C6** — hook à trancher là |
| **Unification double source overlay ↔ fiche** | Groupe **fin de combat** |

### Ambiguïtés laissées ouvertes (C5)

| Point | Traitement |
|---|---|
| **Nettoyage des buffs overlay** (`blessed`, `hunters_mark_caster_id`) à la rupture | Non tranché — effets inertes jusqu'à B4 ; expiration mécanique des buffs = B4 |
| **Save CON avec avantage/désavantage** (conditions futures) | Non tranché — C6 |

---

## Décision 7 — ADR dédié au modèle de combat

### Décision

Le modèle de combat (PV, concentration, `Combatant`, conditions phase 1, persistance, ordonnancement des lots) fait l'objet de **cet ADR-004**. Il **ne prolonge pas** ADR-003 (EventBus générique).

### Justification

Une décision architecturale par ADR. ADR-003 pose le contrat pub/sub in-process ; le modèle de rencontre, les mutations de personnage et les choix de persistance sont un **niveau d'abstraction différent**. Les mélanger obscurcirait la relecture dans un an.

### Alternatives envisagées

| Alternative | Pour | Contre | Verdict |
|---|---|---|---|
| **Extension ADR-003** | Un seul document « événements + combat » | Confond bus technique et modèle métier combat | **Rejetée** |
| **RFC Markdown hors ADR** | Plus léger | Non indexé ; moins de traçabilité | **Rejetée** |
| **ADR-004 dédié** | Clarté ; lien ADR-003 → consomme events, ADR-004 → modèle | Un fichier supplémentaire | **Retenue** |

### Conséquences

- ADR-003 reste la référence pour `EventBus`, `DomainEvent`, handlers.
- ADR-004 est la référence obligatoire avant tout commit C0–C7.
- Les événements combat listés dans ADR-003 (`DamageDealt`, `ConcentrationBroken`, etc.) sont **publiés** conformément à ADR-003, avec payloads définis par le modèle ADR-004.
- **Hiérarchie d'événements** (ADR-003 § Clôture lot C0) : chaque événement combat est une sous-classe **directe** de `DomainEvent` — pas de `CombatEvent` intermédiaire ; champs `combat_id` etc. sur les sous-classes concernées.

---

## Ordonnancement des lots (ROADMAP C0–C7)

### Décision

Le lot **C3 est scindé** :

| Sous-lot | Périmètre | Dépendances |
|---|---|---|
| **C3a** | `apply_damage()` — fonction pure : PV courants, montant, résistances/immunités → PV résultants | Aucune (testable isolément) |
| **C3b** | Résolution d'attaque complète : jet vs CA, critique, calcul dégâts, appel à C3a | C1, C3a |

**Ordre retenu** :

```
C0 → C1 → C3a → C2 → C3b → C5 → C4 → C6 → C7
```

### Justification

Ce qui débloque **C5** (concentration save) et **B4** (effets de sorts) n'est pas la résolution d'attaque complète, mais **`apply_damage` seul**. L'initiative (C2) est de l'**orchestration** qui ne débloque aucun prérequis aval. Extraire **C3a** libère la chaîne dégâts → save CON → tests sans construire jet vs CA avant qu'un tour de jeu existe pour l'exercer.

**C4 avant C6** : C4 (économie d'actions) transforme la capacité à résoudre une attaque en capacité à **jouer un tour complet**. Sans lui, le moteur dispose de fonctions isolées mais d'**aucune boucle jouable**. C6 (registre d'effets et conditions) est de l'**enrichissement**, qui suppose une boucle de tour stable pour être conçu correctement.

### Alternatives envisagées

| Alternative | Pour | Contre | Verdict |
|---|---|---|---|
| **Ordre ROADMAP nominal C2 avant C3** | Flux « naturel » initiative puis attaque | C5/B4 bloqués jusqu'à C3b complet | **Rejetée** |
| **C3 monolithique avant C2** | Attaque complète d'un bloc | Retarde C3a ; tests dégâts noyés dans résolution attaque | **Rejetée** |
| **C3a tôt, C2, puis C3b, C5, C4, C6, C7** | Dégâts testables ; boucle jouable (C4) avant enrichissement (C6) | C6 repoussé après boucle de tour | **Retenue** |
| **C6 avant C4** | Effets/conditions tôt | Pas de boucle de tour stable pour concevoir C6 | **Rejetée** |

### Conséquences

- Premier livrable dégâts : tests unitaires sur `apply_damage` sans `CombatManager`.
- C2 peut publier `InitiativeRolled` / `TurnStarted` sans résolution d'attaque.
- C3b branche `attack_resolution` → C3a → événements ADR-003.

---

## Lot B4 — hors chemin critique MVP combat

### Décision

Le lot **B4** (moteur d'effets de sorts — application mécanique des buffs) **n'est pas** sur le chemin critique du **MVP combat**. Démarrer une rencontre, jouer des tours et infliger des dégâts **ne dépend pas** des effets de sorts structurés.

B4 intervient **après C4** (boucle de tour jouable), comme **première validation** du registre d'effets en amont de **C6** (conditions + effets actifs).

### Ordre des sorts B4

| Ordre | Sort | Raison |
|---|---|---|
| **1** | `hunters_mark` | Cible unique ; +1d6 dégâts ; **aucune extension de `d20.py`** requise ; valide chaîne concentration → modificateur → dégâts |
| **2** | `bless` | +1d4 attaque/sauvegarde ; nécessite support **dés dans les modificateurs de jet** (`d20.py` / `EffectModifier`) |

### Alternatives envisagées

| Alternative | Pour | Contre | Verdict |
|---|---|---|---|
| **B4 parallèle à C1** | Buffs dès le premier prototype | Bloque sur registry + d20 ; retard combat de base | **Rejetée** |
| **`bless` en premier sort B4** | Cas documenté dans COMBAT_PREP | Requiert `1d4` dans modificateurs avant validation dégâts simples | **Rejetée pour premier sort** |
| **B4 après boucle combat ; `hunters_mark` puis `bless`** | Chemin critique minimal ; validation progressive | Effets sorts absents du premier MVP jouable | **Retenue** |

### Conséquences

- MVP combat jouable sans `bless` ni `hex` mécaniques.
- Registre curated (`rules/effects/registry.py` ou équivalent) amorcé par `hunters_mark`.
- Extension `d20.py` pour modificateurs en dés planifiée avant `bless`.

---

## Synthèse des conséquences transverses

| Domaine | Impact |
|---|---|
| **`Character`** | Reste entité persistée ; PV et concentration mutés in-place |
| **`Combatant` / `CombatState`** | Overlay rencontre (initiative, effets runtime, économie d'actions) **sans** duplicate PV |
| **`ActiveEffect`** | Vue dérivée + effets sorts/conditions ; pas source concentration |
| **Persistance** | `personnages` + table `combats` JSON dans `data/bot.db` |
| **Tests** | C3a isolé ; PJ-only ; events ADR-003 |
| **Documentation** | `COMBAT_PREP_MODELE.md` = inventaire ; **ADR-004** = décisions actées ; **ADR-003 § Clôture C0** = contrat EventBus et forme des événements |

---

## Points laissés ouverts (renvois délibérés)

| Point | Traitement |
|---|---|
| **Schéma SQL de la table `combats`** | **Renvoi au lot C7** — les colonnes seront définies lorsque le contenu de `CombatState` sera stabilisé. Un ADR figeant un schéma prématurément produirait une spécification rapidement fausse. |
| **Nom du module conditions phase 1** | Ouvert — principe « module unique dédié » acté (décision 4) ; identifiant de fichier fixé au lot C6. |
| **Mise à jour des documents canoniques** (`ARCHITECTURE.md`, `AGENTS.md`) | Ouvert — hors périmètre de cet ADR ; renvoi ponctuel dans `ARCHITECTURE_TARGET.md` pour la persistance combat. |

---

## Références

- `docs/COMBAT_PREP_MODELE.md` — Inventaire pré-conception (état code, propositions)
- `ROADMAP.md` — Lots C0–C7, Axe B4
- `VISION.md` §5, §9, §10 — Combat API pure, ordre moteur → Web
- [ADR-001](ADR-001%20-%20Pourquoi%20un%20Rule%20Engine.md) — Rule Engine
- [ADR-003](ADR-003%20-%20Pourquoi%20utiliser%20un%20EventBus.md) — EventBus
- `jdr_engine/domain/character/character.py` — Entité persistée
- `jdr_engine/rules/spellcasting/cast.py` — `_apply_healing`, délégation `set_concentration`
- `jdr_engine/rules/spellcasting/concentration.py` — `set_concentration`, `clear_concentration`, `get_active_concentration`
- `jdr_engine/rules/combat/concentration_save.py` — `concentration_save_dc`
- `jdr_engine/rules/spellcasting/state.py` — état spellcasting (emplacements, grimoire)
