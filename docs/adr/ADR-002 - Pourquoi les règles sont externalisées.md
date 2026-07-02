# ADR-002 — Pourquoi les règles sont externalisées

| Attribut | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-07-02 |
| **Décideurs** | Lead Architect, Product Owner |
| **Contexte** | Conception du Compendium et séparation moteur / contenu |

---

## Contexte

Un moteur JDR destiné à évoluer pendant **plusieurs années** avec :

- Plusieurs milliers de sorts
- Plusieurs centaines d'armes, armures, objets magiques
- Des centaines de monstres
- Plusieurs systèmes de règles (D&D 5e, D&D 2024, Pathfinder 2, custom)
- Des interfaces multiples (Discord, Web, mobile, API, Foundry)
- De la documentation, du lore, des illustrations par entité
- Du contenu homebrew ajouté par les MJ

Si les règles restent en Python, **chaque entité de jeu est un changement de code** : review, test, déploiement. À l'échelle visée, c'est ingérable.

---

## Décision

Toutes les **définitions de jeu** sont externalisées dans le **Compendium** :

```
compendium/
  {ruleset_id}/
    manifest.yaml          # Identité et version du ruleset
    config.yaml            # Config système (caractéristiques, tables de niveau…)
    entries/
      races/elf/
        definition.yaml    # ★ Seul fichier lu par le Rule Engine
        lore.fr.md
        lore.en.md
        assets/portrait.png
```

### Principes

1. **Une seule source de vérité** par entité — pas de double arbre `rules/` + `compendium/`
2. Le **Rule Engine ne lit que `definition.yaml`** (métadonnées mécaniques)
3. Les fichiers **lore, traductions, assets** sont consommés par les **Interfaces** via `CompendiumPresenter`
4. Le **personnage persisté** ne stocke que des **identifiants et choix** (`race_id: "elf"`), jamais les règles complètes
5. Les **stats dérivées** (PV max, CA, bonus de maîtrise) sont **recalculées** à la volée — jamais persistées

### Exemple — Personnage persisté vs fiche calculée

**Persisté** (`data/characters/`) :

```yaml
id: "7fcf37cd"
ruleset_id: "dnd5e"
ruleset_version: "1.2.0"
name: "aztaloph"
race_id: elf
class_id: fighter
level: 1
ability_scores: { str: 15, dex: 14, con: 13, int: 12, wis: 10, cha: 8 }
choices: { ... }
inventory: []
xp: 0
```

**Calculé** (jamais sauvegardé) :

```
CharacterSheet ← RuleEngine.build_character_sheet(character)
  → pv_max: 11 (d10 + CON mod)
  → ac: 16 (chain mail)
  → proficiency_bonus: +2
  → traits: [darkvision, fighting_style, ...]
```

---

## Alternatives envisagées

### Alternative A — Règles en base de données (PostgreSQL)

Tables `races`, `classes`, `spells` avec relations SQL.

| Pour | Contre |
|---|---|
| Requêtes puissantes | Édition du contenu = SQL ou admin UI à construire |
| Concurrence | Pas de versioning Git natif |
| | Lore et assets mal modélisés en SQL |
| | Overkill pour la phase actuelle |
| | Modding = accès DB |

**Rejetée pour le Compendium** — réévaluable pour la **persistance des parties** (sessions, combats actifs).

### Alternative B — Double arbre `rules/` + `compendium/`

`rules/dnd5e/races/elf.json` pour le moteur, `compendium/races/elf/lore.md` pour l'UI.

| Pour | Contre |
|---|---|
| Séparation mécanique / narratif explicite | **Duplication d'identifiants** |
| | Risque de drift (race en rules/ mais pas en compendium/) |
| | Deux loaders à maintenir |
| | Confusion pour les auteurs de contenu |

**Rejetée** — un Compendium unifié avec séparation **interne** par type de fichier.

### Alternative C — Fichiers plats JSON (`rules/dnd5e/races/elf.json`)

Un seul JSON par entité, tout mélangé (mécanique + lore + traductions).

| Pour | Contre |
|---|---|
| Simple | Fichiers énormes pour les sorts (description longue) |
| Un fichier = une entité | Mélange moteur / UI |
| | Difficile à traduire (clés imbriquées) |
| | Pas de place pour les assets à côté |

**Rejetée** — structure en **dossier par entité** retenue.

### Alternative D — Compendium unifié par dossier d'entité (choix retenu)

```
entries/races/elf/
  definition.yaml    → Rule Engine
  lore.{locale}.md   → Interfaces
  assets/            → Interfaces
  meta.yaml          → Documentation, tags, auteur (optionnel)
```

| Pour | Contre |
|---|---|
| Une entité = un dossier | Plus de fichiers que du JSON plat |
| Git-friendly (diff par entité) | Convention de nommage à documenter |
| Assets colocalisés | |
| i18n par fichier locale | |
| Moteur ignore lore/assets | |

**Retenue.**

---

## Conséquences

### Positives

- `orc/definition.yaml` ajouté → race disponible moteur + menus Discord automatiquement
- Contenu versionné Git, reviewable en PR
- Homebrew = dossier dans `compendium/homebrew/`
- Traductions indépendantes du moteur (fichiers `lore.fr.md`, `lore.en.md`)
- Rule Studio (futur) génère des dossiers entiers valides

### Négatives / contraintes

- **Migration** des personnages v1 (`"Elfe"` texte libre → `race_id: "elf"`) nécessaire
- **Versionnement ruleset** : un personnage créé en `dnd5e@1.0` peut diverger si le ruleset évolue → voir ADR futur sur compatibilité versions
- **Validation** obligatoire (CI + boot) pour éviter les refs cassées
- Les auteurs de contenu ne doivent **pas éditer `definition.yaml` à la main** — outils `tools/` / Rule Studio recommandés

### Règle d'or

> Si une information décrit **ce qu'une entité EST** (race, sort, arme) → Compendium.  
> Si une information décrit **ce qu'un joueur A CHOISI** (race_id, sorts connus) → Persistance.  
> Si une information est **calculée** (CA, PV max) → Rule Engine, jamais persistée.

---

## Références

- ADR-001 — Rule Engine
- `docs/ARCHITECTURE_V2.md` — Sections Compendium, i18n, versionnement
