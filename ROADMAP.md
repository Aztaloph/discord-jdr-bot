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
  - [ ] Lots 3+ — Classes une par une (martiales, rôdeur, lanceurs complets, classes SRD absentes)
  - [ ] **Après toutes les classes jouables** : catalogue de sorts étendu (SRD curated)
  - [ ] **Après toutes les classes jouables** : préparation / sorts connus (quotas SRD, choix joueur)
- [ ] **ÉTAPE 4 : Système de combat complet** (initiative, tour par tour, PV ennemis) — GROS CHANTIER
