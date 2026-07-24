# Lot B2 / B2-bis — notes de migration schéma v2.0

> Décisions arbitrées : D1 (schema 2.0), D2 (YAML source unique), D4 (`effects[]`), D7 (`saving_throw` sous-objet d'effet).

---

## B2-bis — correction pool mage (juillet 2026)

**Action validée** : retrait de `guidance` du pool cantrip mage (`classes[]` YAML).

| État | Cantrips mage curated | Taille |
|---|---|---|
| Avant B2-bis | fire_bolt, thaumaturgy, guidance, vicious_mockery | 4 |
| **Après B2-bis** | fire_bolt, thaumaturgy, vicious_mockery | **3** |

⚠️ Pool **sous le quota SRD niv. 4+** (4 cantrips) — **aucun remplaçant ajouté** en B2-bis (attente arbitrage utilisateur avant B3).

---

## Audit SRD 2014 — liste mage curated vs grimoire officiel

Référence : liste de sorts **Magicien** du SRD 5e 2014 (OGL). Les ids compendium sont en `snake_case`.

### Cantrips mage (3 restants)

| id compendium | SRD mage ? | Classe(s) d'origine SRD | Verdict |
|---|---|---|---|
| `fire_bolt` | ✅ Oui | Magicien | **Conserver** |
| `thaumaturgy` | ❌ Non | Clerc | **Écart** — candidat retrait |
| `vicious_mockery` | ❌ Non | Barde | **Écart** — candidat retrait |

**Cantrips SRD mage absents du compendium** (candidats remplacement si retrait) :

| id SRD (slug cible) | Nom FR | Déjà dans compendium ? |
|---|---|---|
| `mage_hand` | Main du mage | ⬜ Non |
| `prestidigitation` | Prestidigitation | ✅ (occultiste seulement) |
| `light` | Lumière | ⬜ Non |
| `ray_of_frost` | Trait de givre | ⬜ Non |
| `shocking_grasp` | Poigne électrique | ⬜ Non |
| `minor_illusion` | Illusion mineure | ⬜ Non |
| `acid_splash` | Éclaboussure acide | ⬜ Non |
| `chill_touch` | Contact glacial | ⬜ Non |

**Scénarios si tu valides les retraits** (sans feu vert = rien ne bouge) :

| Action | Pool résultant | Remplaçants SRD requis |
|---|---|---|
| Retirer `thaumaturgy` seul | 2 cantrips | **2** nouvelles fiches (ex. mage_hand + light) |
| Retirer `vicious_mockery` seul | 2 cantrips | **2** nouvelles fiches |
| Retirer les deux | 1 cantrip (fire_bolt) | **3** nouvelles fiches |
| Retirer un + réaffecter `prestidigitation` au mage | variable | 1–2 nouvelles fiches |

### Grimoire mage (8 sorts niv. 1–2)

| id | Niv. | SRD mage ? | Verdict |
|---|---|---|---|
| `chromatic_orb` | 1 | ❌ Non (PHB only) | **Écart** — candidat retrait ou remplacement |
| `burning_hands` | 1 | ✅ Oui | Conserver |
| `detect_magic` | 1 | ✅ Oui | Conserver |
| `magic_missile` | 1 | ✅ Oui | Conserver |
| `shield` | 1 | ✅ Oui | Conserver |
| `scorching_ray` | 2 | ✅ Oui | Conserver |
| `darkness` | 2 | ✅ Oui | Conserver |
| `flaming_sphere` | 2 | ✅ Oui | Conserver |

**Sorts SRD mage niv. 1–2 absents du compendium** (exemples si `chromatic_orb` retiré) : `mage_armor`, `sleep`, `thunderwave`, `find_familiar`, `grease`, `fog_cloud`, `mirror_image`, `misty_step`, `invisibility`, …

### Ensorceleur (hors périmètre B2-bis, pour info)

`guidance` reste dans le pool ensorceleur curated — **également absent de la liste SRD ensorceleur**. Arbitrage séparé en B3.

---

## Dette moteur B4 — registre exhaustif (consolidation juillet 2026)

> **Comportement intérimaire attendu** : texte-placeholder ou branche cast minimale (`effects[]` lu) sans automatisation SRD complète.  
> **Aucune implémentation B4 dans ce registre** — suivi doc uniquement.

| # | Sort / pattern concerné | Nature de la dette | Comportement actuel (cast / affichage) | Cible B4 |
|---|---|---|---|---|
| 1 | **Pattern `utility` + `saving_throw`** — `entangle`, `faerie_fire` | Save mécanique porté sous l'effet (D7) mais sort traité comme `utility` | Cast : texte `utility_effect` ; save/entravé/contour non résolus | Résolution save + état zone |
| 2 | **Pattern `spell_attack` + `auto_hit`** — `magic_missile` | Projectiles sans jet d'attaque | Cast : dégâts auto ; **`slot_scaling.missiles` appliqué** (iso `scorching_ray`) | Comportement auto-hit complet (cibles séparées) |
| 3 | **Pattern cantrip scaling `attacks`** — `eldritch_blast` | Scaling par nombre de rayons, pas seulement `damage_dice` | Cast : 1 instance par défaut ; tiers `attacks` du YAML **non lus** pour multiplier les attaques | Boucle d'attaques selon `cantrip_scaling.tiers[].attacks` |
| 4 | **Pattern `spell_attack` + `invocation`** — `spiritual_weapon` | Attaque initiale + action bonus récurrente | Cast : 1 attaque ; texte `invocation_effect` ; **`slot_scaling.damage_dice` non appliqué** | Entité persistante + réattaques bonus |
| 5 | **Pattern multi-effets `effects[]`** — `vicious_mockery` | Dégâts save + désavantage | Cast : branche `saving_throw` (1er effet) ; désavantage en `utility_effect` **texte seul** | Composer résultat multi-effets (dégâts + désavantage) |
| 6 | **Pattern `buff` texte-placeholder** — `shield`, `bless`, `hunters_mark`, `guidance`, `mage_armor`, **`haste`** | Buffs sans champs structurés | Cast : `buff_effect` affiché ; `haste`/`bless`/`guidance`/`hunters_mark` posent **concentration** si `concentration: true` ; **aucun bonus mécanique** (`haste` : vitesse ×2, +2 CA, action bonus, léthargie = texte) | Buffs structurés + durée/état |
| 7 | **Pattern `ritual` décoratif** — `detect_magic` | Incantation rituelle sans flux dédié | `ritual: true` affiché ; cast consomme un emplacement comme sort normal | Flux rituel (sans emplacement) |
| 8 | **Réaction / interruption** — **`counterspell`** | Sort réaction anti-lancement | Cast : branche `utility` + `utility_effect` (« Réaction — interrompt… ») ; **pas de fenêtre réaction, pas d'interruption** | Moteur réaction + contresort |
| 9 | **Utilitaire anti-magie** — `dispel_magic` | Fin de sorts actifs / test d'incantation | Cast : texte `utility_effect` ; **aucune résolution** | Dispel ciblé + test DD |
| 10 | **Utilitaire mouvement** — `fly` | Vitesse de vol + chute | Cast : texte `utility_effect` ; **`concentration: true` non posée** (iso `detect_magic` en utility) | Vol + chute si fin du sort |
| 11 | **Utilitaire divers** — `darkness`, `hex`, `thaumaturgy`, `druidcraft`, `prestidigitation`, `detect_magic` (hors rituel), etc. | Effets non structurés | Texte `utility_effect` / description ; pas d'automatisation | Selon sort (vision, maléfice, etc.) |
| 12 | **Scaling upcast `damage_dice` non appliqué** — **`burning_hands`**, **`fireball`**, **`lightning_bolt`**, `flaming_sphere`, `hellish_rebuke`, `inflict_wounds`, `chromatic_orb` (ensorceleur) | `slot_scaling.per_slot_above_base.damage_dice` | **Métadonnée + embed** (`mechanics_display`) ; cast : **dégâts base uniquement** (ex. `3d6`, `8d6`) — pas de +1d6 par emplacement au-dessus du niveau de base | Appliquer increment au cast (comme missiles) |
| 13 | **Scaling upcast `damage_dice` non appliqué (soins)** — `cure_wounds`, `healing_word`, `spiritual_weapon` | `healing_dice` / `damage_dice` dans `slot_scaling` | Affichage seulement ; cast : base fixe | Upcast soins/dégâts |
| 14 | **Scaling upcast `missiles` — APPLIQUÉ ✅** — **`scorching_ray`**, **`magic_missile`** | `slot_scaling.per_slot_above_base.missiles` | Cast : **`_resolve_damage_instance_count`** ajoute rayons/dards par emplacement | Maintenir ; référence pour B4 |
| 15 | **Scaling upcast autres clés non appliquées** — `bless` (`extra_targets`), `armor_of_agathys` (`temp_hp`, `cold_damage`) | Clés `slot_scaling` hors dégâts/missiles | Affichage / texte ; cast ignore | Upcast cibles / temp HP / froid |
| 16 | **Concentration persistante incomplète** — `darkness`, `flaming_sphere`, `hex`, `fly`, `haste`, `bless`, etc. | `concentration: true` partiellement exploité | Buff : pose `choices.spellcasting.concentration` ; **utility : pas de pose** ; pas de rupture / sync état | Tracking concentration B4 |
| 17 | **Réaction texte sans flag** — `shield`, `hellish_rebuke` | Sorts réaction décrits en YAML | `shield` : buff ; `hellish_rebuke` : save + note réaction dans `utility_effect` / effet ; **pas de moteur réaction** | Fenêtre réaction + déclencheurs |
| 18 | **SRD note / racial** — `thaumaturgy` (`racial_reference` tiefling) | Métadonnée affichage | Non consommé par le moteur | Optionnel affichage / sorts raciaux |

**Synthèse scaling upcast (demande explicite)** :

| Sort | Clé `slot_scaling` | Statut cast |
|---|---|---|
| `burning_hands` | `damage_dice: 1d6` | ❌ Non appliqué — dette B4 |
| `fireball` | `damage_dice: 1d6` | ❌ Non appliqué — dette B4 |
| `lightning_bolt` | `damage_dice: 1d6` | ❌ Non appliqué — dette B4 |
| `scorching_ray` | `missiles: 1` | ✅ Appliqué (`_resolve_damage_instance_count`) |
| `magic_missile` | `missiles: 1` | ✅ Appliqué (même chemin) |

---

## Patterns de schéma validés (schéma YAML — hors moteur)

Les formes ci-dessous sont **valides en v2.0** ; la colonne « Cible B4 » du tableau ci-dessus indique ce qui manque au moteur.

| Pattern | Exemples compendium | Forme YAML |
|---|---|---|
| P1 — `utility` + `saving_throw` | `entangle`, `faerie_fire` | `effects[].saving_throw.{ability, half_on_save}` |
| P2 — `spell_attack` + `auto_hit` | `magic_missile` | `effects[].auto_hit: true`, `attacks` |
| P3 — cantrip scaling `attacks` | `eldritch_blast` | `cantrip_scaling.tiers[].attacks` |
| P4 — `spell_attack` + `invocation` | `spiritual_weapon` | `effects[].invocation: true` + `invocation_effect` |

---

## Sorts à comportement intérimaire texte (index rapide — voir tableau B4)

Les numéros #1–#7 historiques sont **fusionnés dans le registre B4** (lignes 1–7). `#8 guidance` mage : corrigé B2-bis.

---

## Champ additionnel : `class_pool_order`

Non figé en B1 ; requis pour **iso-comportement** de `preparation.py` (`pool[:quota]`) sans dupliquer les listes dans `spells_catalog.py`. L'ordre est porté par chaque fiche YAML ; `spells_catalog.py` ne fait que dériver.

## Champs `mechanics.save` / `attack_roll` / `damage_dice`

Conservés comme **miroirs d'affichage** (`mechanics_display.py`). Le cast lit `effects[]` exclusivement.

## Prochaine étape B3

1. Arbitrage utilisateur sur écarts audit ci-dessus (retrait **vs** remplacement SRD).
2. Ajout de fiches manquantes **avant** ou **en même temps** que tout retrait qui ferait chuter le pool sous le quota.
3. Ne pas dupliquer les listes dans `spells_catalog.py`.

---

## B3-a — sorts niv. 3 mage (juillet 2026)

**6 fiches** ajoutées (`classes: [wizard]` uniquement) — pool grimoire **14** (= quota niv. 5).

| id | Pattern cast | Scaling emplacement |
|---|---|---|
| `fireball` | `saving_throw` 8d6 feu | `slot_scaling.per_slot_above_base.damage_dice: 1d6` — **métadonnée + affichage** ; calcul à l'incantation = **B4** (comme `burning_hands`) |
| `lightning_bolt` | idem 8d6 foudre | idem |
| `counterspell` | `utility` + texte | Pas de réaction/interruption — **B4** |
| `dispel_magic` | `utility` + texte | Pas de résolution anti-magie — **B4** |
| `fly` | `utility` + texte | Pas de vitesse de vol — **B4** |
| `haste` | `buff` + texte ; `concentration: true` pose l'état concentration existant (iso `bless`) | Effets mécaniques (+2 CA, action bonus…) = **B4** |

**Aucune modification de `cast.py`** dans B3-a.

---

## B3-b — sorts niv. 4 mage Option A (juillet 2026)

**4 fiches** ajoutées (`classes: [wizard]` uniquement) — pool grimoire **18** (= quota niv. 7).

| id | Pattern cast | Placeholder B4 |
|---|---|---|
| `polymorph` | `buff` + texte ; `concentration: true` | Forme bête / stats remplacées — moteur B4 |
| `banishment` | `utility` + sous-objet `saving_throw` (CHA) ; `concentration: true` | Exil planaire — résolution save B4 |
| `dimension_door` | `utility` + texte | Téléportation — texte |
| `ice_storm` | `saving_throw` 4d6+2d8 froid (DEX, half) | Dégâts mixtes contondant/froid — base cast OK ; pas de `slot_scaling` |

**Aucune modification de `cast.py`** dans B3-b.

---

## B3-b — proposition niv. 4 mage (archive doc — juillet 2026)

> **Option A livrée** — voir section ci-dessus.

### Contexte quota (après B3-b, pool grimoire = 18)

| Niv. perso mage | Quota grimoire | Emplacements niv. 4 | Écart pool → quota |
|---:|---:|---|---|
| 5 | 14 | ⬜ | **0** (palier B3-a saturé) |
| 6 | 16 | ⬜ | **+2** |
| **7** | **18** | ✅ (1 emplacement) | **0** (palier B3-b saturé) |
| 8 | 20 | ✅ | +2 |
| 9 | 22 | ✅ | +4 |

**Premier palier où les sorts niv. 4 sont lançables** : niv. perso **7** (quota **18**).  
**Palier intermédiaire** : niv. **6** (quota **16**, sorts niv. 4 au grimoire mais pas encore lançables).

---

### Inventaire SRD complet — sorts niv. 4 mage (23)

Référence : [5thsrd.org — Wizard Spell List](https://5thsrd.org/spellcasting/spell_lists/wizard_spells/).

| # | Slug proposé | Nom FR |
|---|---|---|
| 1 | `arcane_eye` | Œil magique |
| 2 | `banishment` | Bannissement |
| 3 | `black_tentacles` | Tentacules noirs d'Evard |
| 4 | `blight` | Flétrissure |
| 5 | `confusion` | Confusion |
| 6 | `conjure_minor_elementals` | Invocation d'élémentaires mineurs |
| 7 | `control_water` | Contrôle de l'eau |
| 8 | `dimension_door` | Porte dimensionnelle |
| 9 | `fabricate` | Fabrication |
| 10 | `faithful_hound` | Chien fidèle de Mordenkainen |
| 11 | `fire_shield` | Bouclier de feu |
| 12 | `greater_invisibility` | Invisibilité supérieure |
| 13 | `hallucinatory_terrain` | Terrain hallucinatoire |
| 14 | `ice_storm` | Tempête de grêle |
| 15 | `locate_creature` | Localisation de créature |
| 16 | `phantasmal_killer` | Tueur imaginaire |
| 17 | `polymorph` | Métamorphose |
| 18 | `private_sanctum` | Sanctuaire privé de Mordenkainen |
| 19 | `resilient_sphere` | Sphère résiliente d'Otiluke |
| 20 | `secret_chest` | Coffre secret de Léomund |
| 21 | `stone_shape` | Façonnage de la pierre |
| 22 | `stoneskin` | Peau de pierre |
| 23 | `wall_of_fire` | Mur de feu |

---

### Options de cible (nombre de fiches B3-b)

| Option | Nombre | Pool grimoire | Palier quota couvert | Remarque |
|---|---:|---:|---|---|
| **A — recommandée** | **4** | 14 → **18** | Niv. **7** (= 1er lancement niv. 4) | Même logique que B3-a (quota = palier d'emplacement) |
| B — intermédiaire | 2 | 14 → **16** | Niv. **6** | Grimoire partiel avant accès emplacements niv. 4 |
| C — SRD complet niv. 4 | 23 | 14 → **37** | Niv. 20 (44) encore sous quota | Lot lourd ; plutôt B3-c+ |

---

### Option A — 4 sorts proposés (indices `class_pool_order` 14–17)

| # | Slug | Nom FR | Pattern v2.0 prévu | Placeholder B4 |
|---|---|---|---|---|
| 14 | `polymorph` | Métamorphose | `buff` ou `utility` + texte | Forme bête / créature — moteur B4 |
| 15 | `banishment` | Bannissement | `saving_throw` (CHA) + `concentration` | Exil planaire — résolution save B4 |
| 16 | `dimension_door` | Porte dimensionnelle | `utility` | Téléportation — texte |
| 17 | `ice_storm` | Tempête de grêle | `saving_throw` (DEX, half) | 2 zones dégâts froid/impact — base 4d8+2d6 ; **`slot_scaling.damage_dice` si présent = dette B4** (pas de nouveau champ) |

**Alternatives** (remplacement 1:1 dans les 4) : `wall_of_fire` (save DEX, concentration), `greater_invisibility` (buff), `stoneskin` (buff), `blight` (save CON, dégâts).

---

**Feu vert reçu** : Option **A** livrée (`polymorph`, `banishment`, `dimension_door`, `ice_storm`).
