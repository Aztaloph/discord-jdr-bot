# Feuille de route — Discord JDR Bot (D&D 5e SRD 2014)

## Philosophie de design

- Les stats du personnage sont **SACRÉES**. Un joueur ne modifie **JAMAIS** directement ses PV, ses emplacements de sorts, ni ses caractéristiques après la création.
- Tout ce qui touche aux chiffres (PV, slots, effets) est calculé **AUTOMATIQUEMENT** par le moteur, en réaction à une action de jeu.
- Un joueur peut posséder **PLUSIEURS personnages** sur un même serveur, mais n'incarne qu'**UN SEUL personnage actif** à la fois pendant une partie (`/perso-choisir`). Les commandes de jeu (`/roll`, `/sort`, etc.) utilisent ce personnage actif par défaut.
- Un joueur peut **UNIQUEMENT** : choisir ses stats / classe / spécialisation à la **CRÉATION**, choisir son **personnage actif**, et gérer son **inventaire** (jeter / vendre à un PNJ vendeur).
- Chaque MJ héberge sa **PROPRE** instance du bot avec ses propres données. On n'héberge jamais les données d'autrui.

---

## Feuille de route

- [x] Compendium SRD 2014
- [x] Moteur de sorts (Magicien INT, Clerc SAG)
- [x] **ÉTAPE 1a : Fondation stockage (SQLite) + rôle MJ**
- [x] **ÉTAPE 1b : Commande de création de personnage**
- [x] **ÉTAPE 2 : Repos long / court** (commandes réservées au MJ)
- [ ] **ÉTAPE 3 : Compléter les classes** (sorts, compétences, styles de combat, sous-classes)
  - [x] **Lot 0 — Fondations transverses** : schéma `choices`, calculs dérivés, fiche `/perso-afficher`
  - [x] **Lot 1 — Choix à la création** (`/creer-perso` : point buy, compétences, domaine clerc)
  - [x] **Lot 2 — Montée de niveau 2-3** (`/monter-niveau` MJ, PV / emplacements / dés de vie)
  - [x] Lots 3+ — Classes une par une (martiales, rôdeur, lanceurs complets, classes SRD absentes) — TOUTES LES CLASSES SRD 2014 TERMINÉES
  - [ ] **Passe 1 — Enrichissement des sorts** (catalogue SRD curated : effets réels des sorts référencés) — EN COURS
  - [ ] **Passe 2 — Sorts préparés / connus dynamiques** (quotas SRD, filtrage auto par classe, choix joueur au level-up ; recopie grimoire mage = option MJ)
  - [ ] **Passe 3 — Automatisation des aptitudes** (forme sauvage, métamagie, canalisation d'énergie, arme/familier de pacte…)
  - [ ] **Passe 4 — Passe UI / affichage** (libellés, fix limite de caractères des embeds, libellé « Sous-classe (niv. 3) »)
- [ ] **ÉTAPE 4 : Système de combat complet** (initiative, tour par tour, PV ennemis, level-up par XP) — GROS CHANTIER
- [ ] **ÉTAPE 5 : Portage / fix version 2024** (armes, dégâts, actions bonus, sous-classes niv.3…) — TOUT À LA FIN, après le combat
