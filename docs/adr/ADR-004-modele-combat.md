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

- C7 : `combat_repository.py` + migration schéma dans `database.py` (version incrémentée).
- Handler EventBus `CombatAutoSaveHandler` écrit dans `combats`.
- `ARCHITECTURE_TARGET.md` (snapshots fichiers) est **supplanté** par cette décision pour l'implémentation.

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

B4 intervient **après** une boucle combat fonctionnelle (C0–C3b minimum, ideally C5), comme **première validation** du registre d'effets en amont de **C6** (conditions + effets actifs).

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
| **Documentation** | `COMBAT_PREP_MODELE.md` = inventaire ; **ADR-004** = décisions actées |

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
- `jdr_engine/rules/spellcasting/cast.py` — `_apply_healing`, `_set_concentration`
- `jdr_engine/rules/spellcasting/concentration.py` — `set_concentration`, `clear_concentration` (module cible)
- `jdr_engine/rules/spellcasting/state.py` — état spellcasting (emplacements, grimoire)
