# ADR-001 — Pourquoi un Rule Engine

| Attribut | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-07-02 |
| **Décideurs** | Lead Architect, Product Owner |
| **Contexte** | Migration bot Discord → moteur JDR modulaire |

---

## Contexte

Le projet est aujourd'hui un bot Discord dont la logique métier (formules D&D, listes de caractéristiques, validation des races/classes) est **codée en dur dans Python**, principalement dans `bot/cogs/character.py` et `bot/models/character.py`.

Exemples concrets du code actuel :

- Formule de modificateur : `(valeur - 10) // 2` dans `Personnage.modificateur()`
- Liste des 6 caractéristiques : `NOMS_CARAC`, `ABBREV_CARAC` en constantes Python
- Race et classe saisies en texte libre : `"Elfe"`, `"Guerrier"` sans identifiant stable

Objectifs à terme :

- Supporter D&D 5e, D&D 2024, Pathfinder 2, systèmes custom
- Ajouter une race (`orc`) sans modifier une ligne de Python
- Interfaces multiples (Discord, Web, API, CLI, Foundry VTT)
- Milliers de sorts, centaines de monstres, centaines d'objets

---

## Décision

Nous créons un **Rule Engine** indépendant, stateless, situé dans `jdr_engine/rules/`.

Le Rule Engine :

1. **Charge** le Compendium (données externalisées par ruleset)
2. **Valide** l'intégrité référentielle des définitions
3. **Résout** les références entre entités (`trait:darkvision` → définition complète)
4. **Calcule** les statistiques dérivées à partir de l'état d'un personnage + définitions
5. **Expose** une façade publique (`RuleEngine`) consommée par la couche Application

Le Rule Engine **ne contient aucune règle D&D codée en dur**. Il connaît des **mécanismes génériques** (bonus, maîtrise, effet, résistance) — pas des entités (`Elf`, `Fighter`).

---

## Alternatives envisagées

### Alternative A — Règles codées en Python (statu quo)

```python
if race == "elf":
    scores["dex"] += 2
```

| Pour | Contre |
|---|---|
| Simple, rapide | Chaque race/classe = commit + redeploiement |
| Pas de schéma à maintenir | Impossible de supporter multi-rulesets |
| | Non modifiable par la communauté |
| | Couplage total moteur ↔ D&D 5e |

**Rejetée** — plafond de verre immédiat.

### Alternative B — Scripts Python par ruleset (`rules/dnd5e/races/elf.py`)

| Pour | Contre |
|---|---|
| Flexibilité maximale | Chaque entité = code Python (pas data-driven) |
| Typage natif | Pas de validation statique du contenu |
| | Modding communautaire impossible sans exécuter du code arbitraire |
| | Risque sécurité (exec de plugins non contrôlés) |

**Rejetée** — confond contenu et code ; incompatible avec l'objectif « ajouter un JSON sans Python ».

### Alternative C — Moteur de règles interprété (DSL maison)

Un langage dédié : `WHEN race IS elf THEN ADD 2 TO dex`.

| Pour | Contre |
|---|---|
| Extrêmement flexible | Coût de conception et maintenance d'un langage |
| | Courbe d'apprentissage pour les auteurs de contenu |
| | Debugging complexe |
| | Over-engineering pour la phase actuelle |

**Rejetée pour l'instant** — réévaluable si le schéma d'effets YAML s'avère insuffisant (ADR futur).

### Alternative D — Rule Engine + Compendium data-driven (choix retenu)

Données en YAML/JSON, moteur générique d'effets, résolution par références.

| Pour | Contre |
|---|---|
| Contenu sans code | Schéma d'effets à concevoir soigneusement |
| Multi-ruleset natif | Nouveau *type* de mécanique = évolution moteur |
| Validation CI du contenu | Courbe initiale plus élevée |
| Testable sans Discord | |
| Modding / homebrew | |

**Retenue.**

---

## Conséquences

### Positives

- Ajout de `compendium/dnd5e/entries/races/orc/` → race jouable sans Python
- Changement de ruleset = changement de dossier compendium, pas de moteur
- 100 % du Rule Engine testable unitairement
- Séparation claire : **Game Engine** (état mutable) vs **Rule Engine** (calcul stateless)

### Négatives / contraintes

- Le schéma d'**effets génériques** (`EffectProcessor`) est le point critique — mal conçu, on retombe sur du code en dur
- Un **nouveau type de mécanique** (ex. « système de sanité ») nécessitera une évolution du moteur — ce n'est pas entièrement data-driven à l'infini
- Investissement initial : loader, registry, validator, calculator, resolver

### Frontières de responsabilité (rappel)

| Composant | Question |
|---|---|
| **Rule Engine** | « Que dit la règle ? Quelle est la CA de ce personnage ? » |
| **Game Engine** | « Que se passe-t-il ? Infliger 8 dégâts, équiper une épée » |
| **Compendium** | « Quelles sont les données brutes ? » |

---

## Références

- `docs/ARCHITECTURE_V2.md` — Architecture cible complète
- ADR-002 — Externalisation des règles
- ADR-003 — EventBus
