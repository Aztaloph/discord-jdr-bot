# Feuille de route — Discord JDR Bot (D&D 5e SRD 2014)

## Philosophie de design

- Les stats du personnage sont **SACRÉES**. Un joueur ne modifie **JAMAIS** directement ses PV, ses emplacements de sorts, ni ses caractéristiques après la création.
- Tout ce qui touche aux chiffres (PV, slots, effets) est calculé **AUTOMATIQUEMENT** par le moteur, en réaction à une action de jeu.
- Un joueur peut **UNIQUEMENT** : choisir ses stats / classe / spécialisation à la **CRÉATION**, et gérer son **inventaire** (jeter / vendre à un PNJ vendeur).
- Chaque MJ héberge sa **PROPRE** instance du bot avec ses propres données. On n'héberge jamais les données d'autrui.

---

## Feuille de route

- [x] Compendium SRD 2014
- [x] Moteur de sorts (Magicien INT, Clerc SAG)
- [ ] **ÉTAPE 1a : Fondation stockage (SQLite) + rôle MJ** ← EN COURS
- [ ] **ÉTAPE 1b : Commande de création de personnage**
- [ ] **ÉTAPE 2 : Repos long / court** (commande réservée au MJ)
- [ ] **ÉTAPE 3 : Compléter les classes** (sorts, compétences, styles de combat, sous-classes)
- [ ] **ÉTAPE 4 : Système de combat complet** (initiative, tour par tour, PV ennemis) — GROS CHANTIER
