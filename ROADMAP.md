# Feuille de route — Discord JDR Bot (D&D 5e SRD 2014)

## Philosophie de design

- Les stats du personnage sont **SACRÉES**. Un joueur ne modifie **JAMAIS** directement ses PV, ses emplacements de sorts, ni ses caractéristiques après la création.
- Tout ce qui touche aux chiffres (PV, slots, effets) est calculé **AUTOMATIQUEMENT** par le moteur, en réaction à une action de jeu.
- Un joueur peut posséder **PLUSIEURS personnages** sur un même serveur, mais n'incarne qu'**UN SEUL personnage actif** à la fois pendant une partie (`/perso-choisir`). Les commandes de jeu (`/roll`, `/sort`, etc.) utilisent ce personnage actif par défaut.
- Un joueur peut **UNIQUEMENT** : choisir ses stats / classe / spécialisation à la **CRÉATION**, choisir son **personnage actif**, et gérer son **inventaire** (jeter / vendre à un PNJ vendeur).
- Chaque MJ héberge sa **PROPRE** instance du bot avec ses propres données. On n'héberge jamais les données d'autrui.

---

## État du projet (juillet 2026)

| Indicateur | Valeur |
|---|---|
| Tests unitaires | **519** verts (`python -m unittest discover -s tests/unit -p "test_*.py" -q`) |
| Classes SRD 2014 | 12/12 jouables (création + montée de niveau 1–3) |
| Catalogue sorts curated | 28 sorts (9 cantrips + 15 niv. 1 + 4 niv. 2) |
| Derniers commits | P1-fixes-sorts (scorching_ray, hellish_rebuke, métamagie) |

### Travail local non commité (à valider / committer)

Plusieurs lots **P0 → P1c** + correctif libellé autocomplete sont implémentés et testés localement, mais **pas encore poussés sur `main`** :

- Taxonomie lanceurs (`model.py`, `pools.py`, `spell_levels.py`)
- Druide / occultiste / demi-lanceurs (rôdeur, paladin)
- Autocomplete `/sort` enrichi (✨ castable · 🔒 niveau/emplacements · 📘 non préparé)
- Libellé 🔒 « emplacements niv. X épuisés » (vs « niv. X requis »)
- Texte création perso périmé (hint 12 classes SRD)

---

## Feuille de route

- [x] Compendium SRD 2014
- [x] Moteur de sorts (Magicien INT, Clerc SAG → étendu à toutes les classes lanceuses)
- [x] **ÉTAPE 1a : Fondation stockage (SQLite) + rôle MJ**
- [x] **ÉTAPE 1b : Commande de création de personnage**
- [x] **ÉTAPE 2 : Repos long / court** (commandes réservées au MJ)
- [ ] **ÉTAPE 3 : Compléter les classes** (sorts, compétences, styles de combat, sous-classes)
  - [x] **Lot 0 — Fondations transverses** : schéma `choices`, calculs dérivés, fiche `/perso-afficher`
  - [x] **Lot 1 — Choix à la création** (`/creer-perso` : point buy, compétences, domaine clerc)
  - [x] **Lot 2 — Montée de niveau 2-3** (`/monter-niveau` MJ, PV / emplacements / dés de vie)
  - [x] **Lots 3+ — Classes une par une** — **12 classes SRD 2014 terminées**
  - [x] **Passe 1 — Enrichissement des sorts** (catalogue SRD curated : 28 sorts — métadonnées mécaniques + cast instantané)
    - [x] **Lot A — Tours de magie** (9 cantrips)
    - [x] **Lot B — Sorts niv. 1** (15 sorts)
    - [x] **Lot C — Sorts niv. 2** (`scorching_ray`, `darkness`, `spiritual_weapon`, `flaming_sphere`)
  - [ ] **Passe 2 — Sorts préparés / connus dynamiques**
    - [x] **P2a — Moteur & taxonomie** : 3 familles (`KNOWN_FIXED` / `PREPARED` / `WIZARD_HYBRID`), quotas SRD, pools par classe, builds auto à la création / level-up
    - [x] **P2b — Règles par classe** : magicien (grimoire + préparés), clerc/druide (préparés + domaine), barde/ensorceleur/occultiste (connus), rôdeur/paladin (demi-lanceurs préparés, emplacements ⌈niv/2⌉), sorts élargis occultiste Fiélon
    - [x] **P2c — Lancement & affichage** : `/sort` respecte préparé vs grimoire (mage), connu vs lançable (occultiste), autocomplete enrichi, legacy `spells_prepared` sans `spellbook`
    - [x] **P2d — Correctifs lanceurs** (P1-fixes-sorts) : `scorching_ray`, `hellish_rebuke`, confirmation métamagie ensorceleur
    - [ ] **P2e — Choix joueur au level-up** : UI Discord pour sélectionner sorts connus / préparés (aujourd'hui : attribution automatique depuis le pool curated)
    - [ ] **P2f — Magicien** : autocomplete `/sort` strict (cantrips + **préparés** uniquement ; grimoire non préparé = 📘)
    - [ ] **P2g — Outil MJ** : recopie / réinitialisation grimoire mage (persos legacy)
    - [ ] **P2h — Migration MJ** : normaliser les ~12 persos existants vers le schéma `spellcasting` v2 (non automatique au démarrage)
  - [ ] **Passe 3 — Automatisation des aptitudes** (forme sauvage, métamagie à l'incantation, canalisation d'énergie, arme/familier de pacte…)
  - [ ] **Passe 4 — Passe UI / affichage** (libellés, fix limite de caractères des embeds, libellé « Sous-classe (niv. 3) »)
- [ ] **ÉTAPE 4 : Système de combat complet** (initiative, tour par tour, PV ennemis, level-up par XP) — GROS CHANTIER
- [ ] **ÉTAPE 5 : Portage / fix version 2024** (armes, dégâts, actions bonus, sous-classes niv.3…) — TOUT À LA FIN, après le combat

---

## Clarification : pourquoi la Passe 2 n'était pas cochée ?

Les mécaniques **connus / préparés / grimoire** sont bien en place côté **moteur** (familles, quotas, `cast_spell`, fiche perso, autocomplete). Ce qui manque pour cocher la Passe 2 **entièrement** :

1. **Choix joueur** — pas encore d'écran Discord « choisissez X sorts » à la montée de niveau (contrairement à métamagie / sous-classe).
2. **Magicien strict** — le grimoire complet reste visible dans l'autocomplete (marqué 📘) ; le filtrage « préparés seulement » est optionnel (P2f).
3. **Migration & outils MJ** — persos créés avant P2a (ex. Joe le mage sans clé `spellbook`) : repli legacy OK, migration outillée non faite.

---

## Backlog transverse

Items hors périmètre des lots fonctionnels — à traiter en passes dédiées, sans bloquer l'avancement des étapes principales.

| Priorité | Item | Contexte |
|---|---|---|
| 🔵 | **Calcul effectif du `slot_scaling` à l'upcast** (`cast.py`) | Métadonnées + affichage embed OK (Lots B/C) ; calcul réel à l'incantation (ex. +1 rayon `scorching_ray`, +1d8 `spiritual_weapon`) — lot transverse |
| 🔵 | **Tracking de concentration persistant** | `darkness`, `flaming_sphere`, `hex`, `detect_magic` — état `choices.spellcasting.concentration` non posé pour `effect.type: utility` |
| 🔵 | **Log défensif `_sort_autocomplete`** | Diagnostic autocomplete `/sort` (« Échec des options de chargement ») — traçabilité sans masquer les exceptions |
| 🔵 | **Élargissement catalogue curated** | Sorts SRD 2014 hors périmètre actuel (ex. `mirror_image`, `misty_step`, `hold_person`…) — nouvelles entrées compendium + pools classes |
