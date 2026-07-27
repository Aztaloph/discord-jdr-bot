# AGENTS.md — instructions pour les agents IA

Projet : **Discord JDR Bot** — moteur de jeu de rôle D&D 5e (SRD 5.1 **2014 uniquement**).
Langue de travail : **français** (code, commentaires, docstrings, commits, documentation).

Tu démarres sans mémoire des sessions précédentes. Ce fichier et les documents canoniques sont ta seule source de contexte. **Ne déduis rien d'un historique de chat.**

---

## 1. Documents canoniques

| Document | Rôle | À lire |
|---|---|---|
| `AGENTS.md` | Ce fichier — règles de travail | Toujours |
| `VISION.md` | Stratégie : le « pourquoi », décisions arrêtées D1–D8 | Toujours |
| `ROADMAP.md` | Opérationnel : quoi livrer, dans quel ordre, statuts | Toujours |
| `docs/adr/` | Décisions techniques actées (ADR-001/002/003) | Si tu touches l'architecture |
| `docs/ARCHITECTURE_V2.md` | Architecture **cible** — pas l'état actuel | Si tu touches l'architecture |
| `compendium/dnd5e/entries/spells/` (YAML), `docs/SPELL_SCHEMA.md`, `docs/SPELLS_B2_MIGRATION_NOTES.md` | Sorts : source de vérité compendium, schéma v2.0, dette migration | Si tu touches les sorts |
| `docs/COMBAT_ROLL_PREREQUISITES.md` | Prérequis flags `/roll` — **documenté, non implémenté** | Si tu touches les jets |
| `docs/MIGRATION.md` | Journal historique — **s'arrête à la Phase 4.8, périmé** | Contexte seulement |

## 2. Ordre de priorité en cas de contradiction

1. **Le code réel** — l'architecture existante prime sur toute supposition et sur toute documentation.
2. **`VISION.md`** — pour toute question stratégique (cible, périmètre, décisions D1–D8).
3. **`ROADMAP.md`** — pour toute question opérationnelle (quel lot, quel ordre, quel statut).
4. **ADR** — pour les décisions techniques.
5. **`docs/ARCHITECTURE_V2.md`** — cible souhaitée. Son en-tête de statut est périmé ; là où il contredit le code, **le code gagne**.

Une contradiction se **signale dans ton rapport**, elle ne se corrige pas en silence.

## 3. Frontières architecturales (vérifiées dans le code)

- `jdr_engine/` **n'importe jamais** `discord`, `interfaces` ni `bot` (zéro occurrence aujourd'hui — cet invariant doit être préservé).
- Sens des dépendances : `bot/` → `interfaces/` → `jdr_engine/application` → `rules`/`domain`.
- **`bot/` est vivant, pas du code mort.** `main.py` charge les cogs depuis `bot.cogs.*` ; le bot ne démarre pas sans eux. `ARCHITECTURE_V2.md` §14 les étiquette « LEGACY » : c'est une cible, pas l'état actuel. **Ne pas supprimer.**
- `bot/cogs/*` sont des points d'entrée fins qui délèguent à `interfaces/discord/handlers/*`.
- **Aucune règle D&D dans `bot/` ou `interfaces/`.** Les règles vivent dans `jdr_engine/rules/`, les données dans `compendium/`.
- Placeholders réels (1–2 lignes, aucun code) : `jdr_engine/core/events/`, `jdr_engine/core/i18n/`, `jdr_engine/core/config/`, `jdr_engine/core/plugins/`, `jdr_engine/game/`, `plugins/`, `compendium/_schemas/`.
- `jdr_engine/core/assets/` **n'est pas** un placeholder (`resolver.py` est réel et testé).
- `interfaces/api/` et `interfaces/web/` **n'existent pas** — ne pas les créer avant l'ÉTAPE 6 (voir `ROADMAP.md`).
- Les JSON Schema réels sont dans `compendium/schemas/` (et non `_schemas/`, qui est vide).
- Les pools de sorts sont **dérivés du YAML** (`spell_pool_builder.py`) — ne jamais coder une liste de sorts en dur.

## 4. Commandes

**Validées** (exécutées le 2026-07-27, dépôt au commit `bf24622`) :

```bash
# Tests — référence : 645 tests, OK
python -m unittest discover -s tests -p "test_*.py" -q

# Validation du Compendium — référence : [OK] Compendium valide
python tools/validate_compendium.py dnd5e
```

> `python` désigne **l'interpréteur du venv** : `venv\Scripts\python.exe` sous Windows, `venv/bin/python` sous Unix. Active le venv au préalable, ou préfixe la commande par ce chemin.

La CI (`.github/workflows/ci.yml`) exécute `python -m unittest discover -s tests -v` puis `python tools/validate_compendium.py dnd5e`. Variante également vérifiée : 645 tests, OK.

**Indisponibles — ne pas invoquer, ne pas installer :**

| Besoin | État vérifié |
|---|---|
| Lint | **Aucun outil, aucune configuration.** `ruff`, `flake8`, `black` absents du venv ; rien dans `pyproject.toml` ; aucune étape lint en CI. |
| Type-check | **Aucun.** `mypy` absent. |
| Build | **Impossible.** `setuptools` et `build` absents. |
| `pytest` | Déclaré dans `pyproject.toml` (extra `dev` + `[tool.pytest.ini_options]`) mais **non installé**. Utiliser `unittest`. |

Python du venv : **3.14.6**. (`pyproject.toml` exige `>=3.11`, la CI utilise 3.12, le README annonce 3.10+ — divergence connue, non corrigée.)

Framework de tests : **`unittest`**, jamais `pytest`. Un fichier de test par lot, nommé d'après le lot.

## 5. Modification de la documentation

- **Interdit sans accord explicite du mainteneur** : `VISION.md`, `ROADMAP.md`, `docs/ARCHITECTURE_V2.md`, `docs/adr/**`.
- Ces fichiers sont pilotés par le mainteneur et l'agent d'architecture, pas par les agents d'implémentation.
- Toute décision structurelle **doit produire un ADR avant implémentation** (`docs/adr/README.md`).
- Ne jamais dupliquer VISION dans ROADMAP ou inversement : on **référence** (`VISION.md` §5), on ne recopie pas.
- Un chiffre écrit dans un document (nombre de tests, de sorts) doit être **mesuré**, jamais estimé.

## 6. Interdictions structurantes

Issues des décisions arrêtées de `VISION.md` §10 :

1. **Aucune nouvelle fonctionnalité joueur pour Discord** (D2). Les commandes existantes sont maintenues, pas étendues.
2. **Le Combat Engine est une API moteur pure** (D3) : fonctions déterministes + événements. **Aucun rendu Discord ni Web**, aucun embed, bouton ou composant.
3. **Le moteur ne connaît aucune interface** (D4) : publication d'événements, jamais d'appel direct à une UI.
4. **Ne pas démarrer le Combat Engine (ÉTAPE 4) sans RFC approuvée.**
5. **Ne pas créer `interfaces/api/` ni `interfaces/web/`** avant l'ÉTAPE 6.
6. **Ne pas ajouter de dépendance ni d'outil** sans accord explicite.
7. **Ne pas supprimer `bot/`** ni le mode `USE_ENGINE_V2`.
8. Règles issues du **SRD 5.1 2014 uniquement** — le portage 2024 est l'ÉTAPE 5, en toute fin.
9. **Principe d'intégrité des stats** (`ROADMAP.md`) : PV, emplacements et caractéristiques sont **dérivés**, jamais saisis librement.

## 7. Preuve exigée avant d'annoncer une tâche terminée

Ne déclare **jamais** un lot terminé sans coller dans ton rapport :

1. La sortie brute de la commande de tests — les lignes `Ran N tests` **et** `OK`.
2. La sortie de `tools/validate_compendium.py dnd5e` si tu as touché au `compendium/`.
3. Le **delta du nombre de tests** par rapport à la référence (645 au commit `bf24622`). Un lot fonctionnel qui n'augmente pas ce nombre n'a pas livré de tests.

Règles de véracité :

- N'affirme jamais qu'un élément existe, fonctionne ou est terminé sans l'avoir vérifié avec un outil.
- Si tu n'as pas pu vérifier quelque chose, écris explicitement **« non vérifié »**.
- Ne présente pas un fichier créé comme une fonctionnalité fonctionnelle.
- Distingue dans tes rapports : **fait observé**, **incohérence**, **recommandation**, **décision nécessitant l'accord du mainteneur**.

## 8. Git et périmètre

- Branche d'intégration : **`main`**. Une branche par lot : `feat/c1-combat-state`, `feat/b3-sorts-niv5`.
- Commits **Conventional Commits en français**, scope entre parenthèses — convention observée dans l'historique :
  `feat(spells): …`, `fix(level-up): …`, `docs(roadmap): …`, `chore(tooling): …`
- **Ne jamais commiter** `.env`, `config.json`, `data/bot.db`, `venv/`.
- **Ne pas commiter ni pousser sans demande explicite** du mainteneur.
- **Périmètre strict** : ne modifie que les fichiers nécessaires au lot demandé. Si tu découvres un problème hors périmètre, **signale-le, ne le corrige pas**.
- Si le lot demandé s'avère plus large que prévu, **arrête-toi et remonte** au lieu d'élargir seul.
