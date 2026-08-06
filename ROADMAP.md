# Feuille de route — JDR Engine (D&D 5e SRD 2014)

> **ROADMAP.md** est la **source de vérité opérationnelle** (quoi livrer, dans quel ordre, où on en est). La **source de vérité stratégique** (le « pourquoi », l'architecture cible, le modèle) est [`VISION.md`](VISION.md). Ce document ne duplique pas la vision : il s'y réfère.

## Principes directeurs

Trois décisions arrêtées dans [`VISION.md`](VISION.md) contraignent **tout choix de développement** :

1. **Le Combat Engine est une API moteur pure** — fonctions déterministes + événements, **sans aucune interface** (ni Discord, ni Web). Voir VISION.md §5.
2. **Aucune nouvelle fonctionnalité joueur n'est développée pour Discord** — l'effort d'interface va au client Web ; Discord se réduit au social/notifications. Voir VISION.md §3.
3. **Le moteur se termine avant que le Web ne commence** — le Web consomme le moteur ; on ne bâtit l'API puis le client Web qu'une fois le combat moteur stabilisé. Voir VISION.md §9.

## Philosophie de design

### Principe d'intégrité des stats

Un joueur ne fixe **JAMAIS** directement une valeur (PV, emplacements, caractéristiques). Toute évolution passe par un **choix encadré** validé par le moteur, au moment prévu par les règles :

- **Création** — répartition initiale des caractéristiques (point buy, etc.)
- **Montée de niveau** — ASI aux niveaux 4/8/12/16/19 (SRD 2014), choix de classe, sorts appris, sous-classe, etc.

**Distinction clé :**

- ✅ **Autorisé** — sélectionner une amélioration prévue par les règles, que le moteur valide (bornes, cap 20, +2 ou +1/+1) et applique.
- ❌ **Interdit** — toute commande d'édition libre d'une valeur hors du flux création / montée de niveau.

Les **PV** et **emplacements de sorts** restent **dérivés** (calculés par le moteur depuis niveau, classe et caractéristiques), jamais saisis à la main. Tout ce qui touche aux chiffres en jeu (PV, slots, effets) est recalculé **automatiquement** par le moteur en réaction à une action de jeu.

- Un joueur peut posséder **PLUSIEURS personnages** sur un même serveur, mais n'incarne qu'**UN SEUL personnage actif** à la fois pendant une partie (`/perso-choisir`). Les commandes de jeu (`/roll`, `/sort`, etc.) utilisent ce personnage actif par défaut.
- Un joueur peut **UNIQUEMENT** : faire ses choix encadrés à la **création** et à la **montée de niveau**, choisir son **personnage actif**, et gérer son **inventaire** (jeter / vendre à un PNJ vendeur).
- Chaque MJ héberge sa **PROPRE** instance du bot avec ses propres données. On n'héberge jamais les données d'autrui.

---

## État du projet (août 2026)

| Indicateur | Valeur |
|---|---|
| Tests unitaires | **835** verts (`python -m unittest discover -s tests -p "test_*.py" -q`) |
| Classes SRD 2014 | 12/12 jouables (création + montée de niveau 1–20 full casters, ASI 5 paliers) |
| Catalogue sorts curated | **42** sorts (schéma v2.0 ; grimoire mage **18** = quota niv. 7) |
| Derniers commits | ADR-006 A+B+C (`c09a89b`→`94156f4`) ; ROADMAP/README août 2026 ; ADR-005 ; B4 bless/hunters_mark |

---

## Feuille de route

- [x] Compendium SRD 2014
- [x] Moteur de sorts (Magicien INT, Clerc SAG → étendu à toutes les classes lanceuses)
- [x] **ÉTAPE 1a : Fondation stockage (SQLite) + rôle MJ**
- [x] **ÉTAPE 1b : Commande de création de personnage**
- [x] **ÉTAPE 2 : Repos long / court** (commandes réservées au MJ)
- [ ] **ÉTAPE 3 : Compléter les classes** (sorts, compétences, styles de combat, sous-classes) — 🚧 **en cours** (VISION.md §9, ordre d'exécution 1) ; travail restant = **Passe 3**, **Passe 4**, **Axe A3/A4**, **Axe B3/B4** (détail Axes ci-dessous)
  - [x] **Lot 0 — Fondations transverses** : schéma `choices`, calculs dérivés, fiche `/perso-afficher`
  - [x] **Lot 1 — Choix à la création** (`/creer-perso` : point buy, compétences, domaine clerc)
  - [x] **Lot 2 — Montée de niveau 2-3** (`/monter-niveau` MJ, PV / emplacements / dés de vie)
  - [x] **Lots 3+ — Classes une par une** — **12 classes SRD 2014 terminées**
  - [x] **Passe 1 — Enrichissement des sorts** (catalogue SRD curated : 28 sorts — métadonnées mécaniques + cast instantané)
    - [x] **Lot A — Tours de magie** (9 cantrips)
    - [x] **Lot B — Sorts niv. 1** (15 sorts)
    - [x] **Lot C — Sorts niv. 2** (`scorching_ray`, `darkness`, `spiritual_weapon`, `flaming_sphere`)
  - [x] **Passe 2 — Sorts préparés / connus dynamiques**
    - [x] **P2a — Moteur & taxonomie** : 3 familles (`KNOWN_FIXED` / `PREPARED` / `WIZARD_HYBRID`), quotas SRD, pools par classe, builds auto à la création / level-up
    - [x] **P2b — Règles par classe** : magicien (grimoire + préparés), clerc/druide (préparés + domaine), barde/ensorceleur/occultiste (connus), rôdeur/paladin (demi-lanceurs préparés, emplacements ⌈niv/2⌉), sorts élargis occultiste Fiélon
    - [x] **P2c — Lancement & affichage** : `/sort` respecte préparé vs grimoire (mage), connu vs lançable (occultiste), autocomplete enrichi, legacy `spells_prepared` sans `spellbook`
    - [x] **P2d — Correctifs lanceurs** (P1-fixes-sorts) : `scorching_ray`, `hellish_rebuke`, confirmation métamagie ensorceleur
    - [x] **P2e — Re-préparation joueur (repos long)** : `/preparer-sorts` (clerc, druide, paladin), pool fermé + quota moteur, flag `prepared_rechoice_pending`
    - [x] **P2f — Magicien** : autocomplete `/sort` strict (cantrips + **préparés** uniquement ; grimoire visible sur `/perso-afficher` et `/preparer-sorts`)
    - [x] **P2g — Outil MJ** : `/reset-grimoire` — rebuild grimoire + cantrips + préparés (persos legacy) ; `reset_wizard_grimoire_on_guild()` réutilisable par P2h
    - [x] **P2h — Migration MJ** : `/migrer-grimoires` — batch dry-run + confirm, `migrate_wizard_grimoires_on_guild()` (best-effort par perso, re-scan au clic)
  - [x] **Lot Level-up 4+ (ASI)** — full casters niv. 1–20
    - [x] `MAX_CHARACTER_LEVEL = 20`
    - [x] `requires_asi_at_level` (4/8/12/16/19), `validate_asi`, `AsiDistributionView`
    - [x] Tables progression niv. 6–20 (A1), correction slot niv. 4 (A1-bis), cap + tests 5→20 (A2)
  - [ ] **Passe 3 — Automatisation des aptitudes** (forme sauvage, métamagie à l'incantation, canalisation d'énergie, arme/familier de pacte…)
  - [ ] **Passe 4 — Passe UI / affichage** (libellés, fix limite de caractères des embeds, libellé « Sous-classe (niv. 3) »)
- [ ] **ÉTAPE 4 : Système de combat** — 🚧 **boucle moteur livrée** (C0–C7, ADR-004/005) ; dettes ouvertes = effets au-delà de `bless`/`hunters_mark`, `prone`, movement inerte. **API moteur pure** (fonctions + events), **aucun rendu Discord/Web**. Voir [`VISION.md`](VISION.md) §5.
  > Prérequis techniques : **EventBus** (ADR-003 ✅), **Game Engine** (`CombatManager`, ADR-004 ✅), **Rule Engine** jets/dégâts ✅. Chaque lot ci-dessous est **livrable et testable sans interface**.
  - [x] **C0 — EventBus & socle** : `EventBus` in-process typé + `DomainEvent` (ADR-003), capture de test ; ossature `Game Engine` combat.
  - [x] **C1 — Modèle d'état de combat** : `CombatManager` — participants, PV/CA, ordre, tour courant ; état persistable (blob JSON SQLite).
  - [x] **C2 — Initiative** : jets, tri, événements `CombatStarted` / `InitiativeRolled` / `TurnStarted` / `RoundStarted`.
  - [x] **C3 — Résolution d'attaque & sorts** : jet vs CA + dégâts, attaque/sauvegarde de sort (`AttackRollResolved`, `DamageDealt`, `SavingThrowResolved`).
  - [x] **C4 — Économie d'actions** : action / action bonus / réaction / mouvement par tour, validation des dépenses. *(dette : budget `movement` inerte — ADR-004)*
  - [x] **C5 — Concentration (combat)** : rupture sur dégâts (sauvegarde CON), nettoyage overlay concentration. *(horloge durée rounds : ADR-006 ✅)*
  - [x] **C6 — Conditions en combat** : application/retrait phase 1 (`frightened`, `poisoned`), impact jets via `collect_*`. *(dette : `prone`, conditions → `ActiveEffect` — hors ADR-006)*
  - [x] **C7 — Service & persistance** : `CombatService`, journal événementiel, auto-save handler. *(dette : `_persist()` handler-only — post-C7)*
  - [x] **ADR-005 — Fin de rencontre** : sync PV/concentration à `close_combat`, auto-close `advance_turn`, encounter-scoped conditions.
  - [x] **ADR-006 — Effets actifs unifiés** (doc `c48d9b6` ; impl. A+B+C `c09a89b`→`94156f4`, poussé sur `main`) : `ActiveEffect`, horloge `round_number`, registre `rules/effects/`, migration `bless`/`hunters_mark`, blob `COMBAT_STATE_VERSION` **2**, adaptateurs `collect_*`, persistance consolidée.
- [ ] **ÉTAPE 6 : API (REST + WebSocket)** — 🔜 nouveau (VISION.md §9, ordre 3). `interfaces/api/` expose `CharacterService`, `CombatService`, `CompendiumService` et **pousse les événements EventBus** vers les clients. Objectif : contrat unique consommé par le Web.
- [ ] **ÉTAPE 7 : Client Web (interface de jeu principale)** — 🔜 nouveau (ordre 4). Fiche/tableau de bord, onglets, magie, inventaire, **HUD de combat**, écran MJ. Spécification UX : VISION.md §4.
- [ ] **ÉTAPE 8 : Discord minimal** — 🔜 nouveau (ordre 5). Réduction au social : chat, lancement de partie, `/personnage` → Web, notifications (via EventBus). Voir VISION.md §3.
- [ ] **ÉTAPE 9 : Contenu & carte** — 🔭 long terme (ordre 6). Campagnes, packs d'assets, carte/VTT, base marketplace. Voir VISION.md §4.5 et §8.
- [ ] **ÉTAPE 5 : Portage / fix version 2024** (armes, dégâts, actions bonus, sous-classes niv.3…) — ⏸️ **TOUT À LA FIN** (ordre 7), après le combat **et** le Web

---

## Axe A — Progression des personnages (mécanique)

- [x] **A1** — Tables niv. 6–20 (emplacements, cantrips, connus, grimoire, préparés, maîtrise) — validé SRD.
- [x] **A1-bis** — Correction slot niv. 3 fantôme au niveau 4.
- [x] **A2** — Cap niveau 5→20 + ASI paliers 8/12/16/19 + tests montée 5→20.
- [ ] **A3** — Demi-casters (paladin, rôdeur) + non-casters. Tables de progression dédiées.
- [ ] **A4** — Occultiste (Pact Magic) — logique d'emplacements distincte.

## Axe B — Sorts (contenu + moteur d'effets)

- [x] **B1** — Inventaire de l'existant + schéma de fiche de sort → `docs/SPELLS_INVENTORY.md`, `docs/SPELL_SCHEMA.md`
- [x] **B2** — Schéma v2.0 (`effects[]`, `classes[]`, `saving_throw` sous-objet) + migration 28 sorts + `spells_catalog` dérivé YAML → `docs/SPELLS_B2_MIGRATION_NOTES.md`
- [x] **B2-bis** — Retrait `guidance` du pool cantrip mage + audit SRD (écarts documentés, pas d'autre suppression)
- [x] **B2-ter** — Pool mage SRD : 4 cantrips + 8 grimoire (`mage_hand`, `light`, `ray_of_frost`, `mage_armor` ; retraits mage `thaumaturgy`, `vicious_mockery`, `chromatic_orb`)
- [x] **B3-a** — +6 sorts niv. 3 mage (pool grimoire 14 = quota niv. 5)
- [x] **B3-b** — +4 sorts niv. 4 mage Option A (pool grimoire 18 = quota niv. 7)
- [ ] **B3** — Élargissement catalogue (suite niv. 5+, autres classes)
- [ ] **B4** — Moteur d'effets : dégâts, jets de sauvegarde, **application mécanique des buffs et conditions**.
  - [x] **B4a+B4b** — `hunters_mark` : +1d6 dégâts, nettoyage overlay concentration
  - [x] **B4c+B4d** — `bless` : +1d4 attaque/sauvegarde via `roll_bonus_dice`
  - [x] **ADR-006** — Registre `ActiveEffect`, horloge combat, persistance blob (A+B+C ✅)
  - [x] **B4e** — `hex` : bonus +1d6 dégâts de sort via `spell_damage` (`cast_spell_attack` / `cast_spell_save`)
  - [x] **B4f** — `shield` : horloge ``rounds`` banc de test (approximation durée, sans +5 CA)
  - [ ] **Suite B4** — autres buffs/conditions via registre
  > **Invariant B4 (dégâts de sort en combat)** : tout nouveau chemin qui applique des dégâts de sort en combat passe par `cast_spell_attack` / `cast_spell_save`, ou appelle `apply_damage(..., spell_damage=True)`. Vérification : `grep apply_damage` dans `jdr_engine/`.
  > **Concentration persistante (Lot 1 ✅)** : pose/remplacement/affichage/repos hors combat. **Rupture CON en combat (C5 ✅)**. **Horloge round (ADR-006 ✅)**.

---

## Clarification : Passe 2 — terminée ✅

Tous les jalons P2a–P2h sont livrés. Grimoire mage : consultable via **`/perso-afficher`** / **`/perso-mp`** (`format_spellcasting_detail`) et **`/preparer-sorts`** (pool = grimoire) ; **`/sort`** autocomplete = cantrips + préparés seulement (P2f).

## Lot Level-up 4+ (ASI) — terminé ✅

Chaîne validée : ASI **5 paliers** (4/8/12/16/19), cap **niv. 20** full casters, cantrip scaling 2d10/3d10/4d10, UI **`AsiDistributionView`**.

**Prochain jalon opérationnel** (dans l'ÉTAPE 3) : **Axe B3** (élargissement catalogue) ou **Axe A3** (demi-casters).
**Prochain chantier combat** : extension **B4** (registre — `hex`, durées rounds) ou dettes ADR-004 (`prone`, movement C4).
**ÉTAPE 6 (API REST)** : `interfaces/api/` existe (banc de test DTO) — extension WebSocket et contrat client = après stabilisation combat moteur.

---

## Backlog transverse

Items hors périmètre des lots fonctionnels — à traiter en passes dédiées, sans bloquer l'avancement des étapes principales.

| Priorité | Item | Contexte |
|---|---|---|
| 🔵 | **Edge cap-20 ASI (base 18 vs 19 + racial)** | Invariant cap effectif ≤ 20 démontré ; cas limite UI/validation à durcir en passe dédiée |
| 🔵 | **Scaling upcast `slot_scaling` — clés B4** (`extra_targets`, `temp_hp`, `cold_damage`) | `missiles` / `damage_dice` / `healing_dice` livrés dans `cast.py` ; reste ouvert : `armor_of_agathys` (PV temp., dégâts de contact) — **Axe B4** |
| 🔵 | **Concentration — durées et effets mécaniques** | Lot 1 ✅ hors combat ; rupture CON C5 ✅ ; horloge round ADR-006 ✅ ; **`bless`/`hunters_mark` via registre** ADR-006 A–B ✅. **Ouvert** : autres sorts à durée (`hex`, etc.) |
| 🔵 | **`CharacterSheet.trait_ids` contient des libellés, pas des ids** | `calculator.py` assigne `trait_ids = resolve_race_trait_labels()` (libellés FR) ; les vrais ids sont dans `resolve_race_traits()` (`entry_id`). DTO n'expose que `trait_names`. Corriger `build_character_sheet` + tests. |
| 🔵 | **Log défensif `_sort_autocomplete`** | Diagnostic autocomplete `/sort` (« Échec des options de chargement ») — traçabilité sans masquer les exceptions |
| 🔵 | **Élargissement catalogue curated (B3)** | 42 sorts actuels vs quotas SRD niv. 20 — voir `docs/SPELLS_INVENTORY.md` |
| 🔵 | **Blobs combat v1** | `CombatStateVersionError` au rechargement (pas de migration) — politique : MJ recrée la rencontre ; réévaluer si combats longs persistants |
