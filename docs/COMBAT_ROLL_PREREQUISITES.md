# Validation prérequis — flags combat `/roll` (Phase 4.8+)

> **Statut** : documenté uniquement — **non implémenté** (Bug 2, juillet 2026).  
> Les flags fonctionnent actuellement sur **tout personnage** sans contrôle classe/niveau.

Source des règles : **SRD 5.1 version 2014** uniquement.

---

## Tableau des prérequis à valider (futur)

| Flag `/roll` | Flag interne | Classe requise | Niveau min. | Feature Compendium | Autres conditions |
|---|---|---|---|---|---|
| `arme_distance` | `ranged_weapon` | Guerrier (`fighter`) | 1 | Style de combat **Archerie** | `choices.fighting_style == "archery"` |
| `rage` | `rage_active` | Barbare (`barbarian`) | 1 | `rage` | État Rage (bonus action) ; repos long entre Rages (niv.1-2) |
| `impetueux` | `reckless` | Barbare (`barbarian`) | 2 | `reckless_attack` | 1re attaque FOR mêlée du tour |
| `attaque_sournoise` | `sneak_attack_eligible` | Roublard (`rogue`) | 1 | `sneak_attack` | Toucher, finesse/distance, avantage OU allié à 1,5 m sans désavantage ; 1×/tour |

---

## Traits raciaux (hors flags — automatiques si `perso` + d20)

| Trait | Condition | Validation future |
|---|---|---|
| Chanceux (Halfelin) | `race_id == halfling` | Toujours si race halfelin |
| Brave (Halfelin) | Sauvegarde vs `frightened` | Contexte condition à passer |
| Ennemi juré / Explorateur-né (Rôdeur) | Flags contexte pistage/terrain | Classe + niveau + choix joueur |

---

## Comportement actuel (sans validation)

- Tout flag peut être activé sur **n'importe quel perso**.
- L'**affichage** « Traits actifs » apparaît si le flag est coché (ex. impétueux).
- L'**effet mécanique** du hook ne s'applique que si la feature existe dans le Compendium pour ce personnage (ex. Archerie sans style → pas de +2).

---

## Comportement cible (Phase ultérieure)

1. **Erreur explicite** si flag incompatible (ex. `rage:True` sur Guerrier).
2. **Avertissement** (embed jaune) si niveau insuffisant (ex. impétueux niv. 1 Barbare).
3. **Choix manquants** signalés (ex. Archerie sans `fighting_style` défini).

---

## Notation d20 / avantage (SRD 2014)

| Saisie joueur | Comportement attendu |
|---|---|
| `d20+4` + `impetueux:True` | Bot lance 2d20, **garde le plus haut** + mod |
| `2d20+4` | Normalisé en avantage (meilleur gardé) — **jamais somme** |
| Mode « Avantage » + `d20` | Idem : 2d20, meilleur gardé |

---

*Dernière mise à jour : Phase 4.8 bugfix — juillet 2026.*
