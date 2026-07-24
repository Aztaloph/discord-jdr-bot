# Schéma de fiche de sort — Lot B1 (spec, sans implémentation)

> **Objectif** : figer le format cible pour B2 (migration YAML + validation) et B3 (élargissement catalogue).  
> Compatible avec le modèle actuel `SpellMechanics` et la règle **`min(quota_SRD, pool_classe)`**.

---

## 1. Structure document (proposée)

```yaml
schema_version: "2.0"          # obligatoire — incrément B2
type: spell                    # obligatoire
id: fire_bolt                  # obligatoire — slug stable, = dossier compendium
name:                          # obligatoire
  fr: Trait de feu
  en: Fire Bolt
classes:                       # obligatoire B2+ — remplace la dispersion spells_catalog
  - wizard
  - sorcerer
mechanics: { ... }             # obligatoire — voir §2
```

**Localisation cible** (inchangée) : `compendium/dnd5e/entries/spells/<id>/definition.yaml`

**Pools runtime** : en B2, `spells_catalog.py` devient une **vue dérivée** (générée ou construite depuis `classes[]`) plutôt qu'une source parallèle.

---

## 2. Référence des champs — `mechanics`

| Champ | Obligatoire | Type | Exemple | Moteur aujourd'hui | Rôle |
|---|---|---|---|---|---|
| `level` | **Oui** | `int` 0–9 | `0` (cantrip), `2` | ✅ Cast, slots, filtres pool | Niveau d'emplacement du sort |
| `school` | **Oui** | `string` (enum) | `evocation` | Affichage | École de magie SRD |
| `casting_time` | **Oui** | `i18n string` ou `{fr, en}` | `"1 action"` | Affichage | Temps d'incantation |
| `range` | **Oui** | `i18n string` | `"36 mètres"` | Affichage | Portée |
| `components` | **Oui** | `object` | `{verbal: true, somatic: true, material: false}` | Affichage | Composantes V/S/M |
| `components.material_description` | Optionnel | `i18n string` | `"poussière de diamant..."` | Affichage | Détail composante M |
| `duration` | **Oui** | `i18n string` | `"Instantané"` | Affichage | Durée |
| `concentration` | **Oui** | `bool` | `true` | Affichage ; B4 tracking | Concentration requise |
| `ritual` | Optionnel (déf. `false`) | `bool` | `true` | ⬜ Non exploité | Incantation rituelle |
| `description` | **Oui** | `i18n string` | texte SRD | Affichage | Description joueur |
| `attack_roll` | Optionnel | `bool` | `true` | Cast (heuristique) | Indique attaque de sort |
| `save` | Optionnel | `string` ou `null` | `DEX`, `WIS` | Affichage | Jet de sauvegarde « fiche » |
| `damage_dice` | Optionnel | `string` ou `null` | `2d6` | Affichage | Résumé dégâts (miroir effect) |
| `damage_type` | Optionnel | `string` ou `null` | `fire` | Affichage + cast | Type de dégâts |
| `cantrip_scaling` | Optionnel | `object` | voir §4 | ✅ Cast cantrip | Scaling par niv. **personnage** |
| `slot_scaling` | Optionnel | `object` | voir §5 | ⚠️ Partiel | Scaling par niv. **emplacement** |
| `effect` | **Oui** | `object` | voir §3 | ✅ Cast | Effet exécutable |
| `buff_effect` | Optionnel | `i18n string` | texte buff | Affichage | Effet buff non structuré |
| `utility_effect` | Optionnel | `i18n string` | texte utilitaire | Affichage | Effet utilitaire non structuré |

### Énumération `school` (SRD 2014)

`abjuration`, `conjuration`, `divination`, `enchantment`, `evocation`, `illusion`, `necromancy`, `transmutation`

---

## 3. Bloc `effect` (obligatoire) — par type

Champ discriminant : **`effect.type`** (obligatoire).

### 3.1 `spell_attack`

| Champ | Obligatoire | Type | Exemple |
|---|---|---|---|
| `type` | Oui | `"spell_attack"` | |
| `attack_type` | Optionnel | `ranged` \| `melee` | `ranged` |
| `damage` | Oui* | notation dés | `1d10`, `2d6` |
| `damage_type` | Oui* | string | `fire` |
| `attacks` / `instances` | Optionnel | `int` | `3` (scorching ray) |
| `auto_hit` | Optionnel | `bool` | `true` (magic missile) |
| `add_ability_mod` | Optionnel | `bool` | `false` |

\* Obligatoire si le sort inflige des dégâts.

**Moteur** : jets d'attaque, dés de dégâts, scaling cantrip, scaling missiles (`slot_scaling.per_slot_above_base.missiles`).

### 3.2 `saving_throw`

| Champ | Obligatoire | Type | Exemple |
|---|---|---|---|
| `type` | Oui | `"saving_throw"` | |
| `ability` | Oui | `str\|dex\|con\|int\|wis\|cha` | `dex` |
| `damage` | Oui* | notation dés | `3d6` |
| `damage_type` | Oui* | string | `fire` |
| `half_on_save` | Optionnel (déf. `true`) | `bool` | `true` |
| `reaction` | Optionnel | `bool` | `true` (hellish rebuke) |

**Moteur** : DD = 8 + maîtrise + mod carac. ; demi-dégâts si save réussie.

### 3.3 `healing`

| Champ | Obligatoire | Type | Exemple |
|---|---|---|---|
| `type` | Oui | `"healing"` | |
| `healing` | Oui | notation dés | `1d8` |
| `add_ability_mod` | Optionnel (déf. `true`) | `bool` | `true` |

### 3.4 `buff` / `utility`

| Champ | Obligatoire | Type | Exemple |
|---|---|---|---|
| `type` | Oui | `"buff"` ou `"utility"` | |
| (effet structuré B4) | Optionnel | TBD | — |

**Aujourd'hui** : texte libre via `buff_effect` / `utility_effect` ; pas d'automatisation (B4).

---

## 4. `cantrip_scaling` (optionnel, cantrips uniquement)

```yaml
cantrip_scaling:
  tiers:
    - character_level: 1
      damage_dice: 1d10
    - character_level: 5
      damage_dice: 2d10
    - character_level: 11
      damage_dice: 3d10
    - character_level: 17
      damage_dice: 4d10
```

| Champ tier | Obligatoire | Type | Exemple |
|---|---|---|---|
| `character_level` | Oui | `int` 1–20 | `5` |
| `damage_dice` | Optionnel* | string | `2d10` |
| `attacks` | Optionnel* | `int` | `2` (eldritch blast) |

\* Au moins un de `damage_dice` ou `attacks`.

**Moteur** : `resolve_cantrip_scaling_tier(mechanics, character.level)` → remplace `effect.damage` / nombre d'attaques au cast.

**Interdit** : `cantrip_scaling` si `level > 0`.

---

## 5. `slot_scaling` (optionnel, sorts niv. 1+)

```yaml
slot_scaling:
  per_slot_above_base:
    missiles: 1              # scorching_ray : +1 rayon / niveau au-dessus du 2
    damage_dice: 1d8         # spiritual_weapon (cible B4)
    healing_dice: 1d8        # cure_wounds
    temp_hp: 5               # armor_of_agathys
```

| Clé increment | Type | Exemple sort | État moteur |
|---|---|---|---|
| `missiles` | `int` | scorching_ray | ✅ Appliqué |
| `damage_dice` | string | spiritual_weapon | ⬜ Affichage seulement |
| `healing_dice` | string | cure_wounds | ⬜ Affichage seulement |
| `temp_hp` / `cold_damage` | `int` | armor_of_agathys | ⬜ Affichage seulement |

---

## 6. Champ `classes` (nouveau — B2)

| Champ | Obligatoire | Type | Exemple |
|---|---|---|---|
| `classes` | **Oui** (B2+) | `list[string]` | `[wizard, sorcerer]` |

**Rôle** : liste fermée des classes SRD pouvant apprendre / préparer ce sort.  
**Remplace** la duplication manuelle dans `spells_catalog.py`.

**Classes valides** : `wizard`, `cleric`, `druid`, `bard`, `sorcerer`, `warlock`, `ranger`, `paladin`

---

## 7. Cohérence avec `min(quota, catalogue)`

### Règle actuelle (conservée)

```
cantrips_appris   = pool_cantrips_classe[: min(quota_cantrip(niv.), len(pool))]
grimoire_mage    = pool_grimoire[: min(quota_grimoire(niv.), len(pool))]
sorts_connus     = pool_connus[: min(quota_connus(niv.), len(pool))]
```

- **Quota** : tables SRD dans `model.py` + `get_max_spell_slots` pour les emplacements.
- **Catalogue** : sorts dont `id` ∈ pool classe **et** entrée compendium valide.

### Évolution du test `test_curated_pool_caps_spellbook_and_cantrips_before_srd_quota`

| Phase | Comportement test |
|---|---|
| **Aujourd'hui (A2)** | Assert `len(grimoire) == 8 < 44` et `len(cantrips) == 4 < 5` au niv. 20 |
| **B3 partiel** | Quand `len(pool) >= quota(niv.)` pour un palier donné, assert égalité stricte au quota |
| **B3 complet** | Remplacer l'assert « strictement inférieur » par « `<= quota` et `== min(quota, len(pool))` » ; test dédié par palier (ex. niv. 3 = égalité, niv. 20 = plafond pool tant que pool < quota) |

**Recommandation B3** : scinder en deux tests :

1. `test_spell_list_respects_srd_quota_cap` — toujours `len <= quota`
2. `test_spell_list_fills_quota_when_pool_large_enough` — activé quand le catalogue couvre le quota

---

## 8. Cartographie moteur ↔ champs (résumé)

| Besoin moteur | Champs lus |
|---|---|
| Consommer un emplacement | `mechanics.level` + `get_max_spell_slots(class, character.level)` |
| Attaque / DD sort | Scores effectifs + maîtrise (`get_spellcasting_stats`) — **pas** dans la fiche |
| Dégâts cantrip scaling | `cantrip_scaling.tiers` + `character.level` |
| Dégâts / soins base | `effect.damage` / `effect.healing` |
| Jets de sauvegarde | `effect.type=saving_throw`, `effect.ability`, `effect.half_on_save` |
| Upcast rayons | `slot_scaling.per_slot_above_base.missiles` |
| Autocomplete / cast autorisé | Pool classe + préparé/grimoire/connus (persistance `choices.spellcasting`) |
| Embed référence | `school`, `casting_time`, `range`, `components`, `duration`, `concentration`, `description`, scaling summaries |

**Champs purement descriptifs aujourd'hui** : `ritual`, `buff_effect`, `utility_effect`, la plupart des clés `slot_scaling` hors `missiles`, `mechanics.save` quand `effect.type ≠ saving_throw`.

---

## 9. Décisions ouvertes — arbitrage requis avant B2

| # | Sujet | Options | Impact |
|---|---|---|---|
| **D1** | **`schema_version` 1.0 → 2.0** | Incrément vs conserver 1.0 | Migration B2, validateur compendium |
| **D2** | **Classes dans YAML vs `spells_catalog.py`** | Source unique YAML (`classes[]`) recommandé | Évite divergence guidance-mage |
| **D3** | **Format `slot_scaling`** | Garder `per_slot_above_base` vs table explicite par niveau d'upcast | Complexité B4 |
| **D4** | **Sorts multi-effets** | Un seul `effect.type` vs liste `effects[]` | ex. `vicious_mockery` (dégâts + désavantage) |
| **D5** | **Concentration** | Bool seul vs `{required: true, max_duration: ...}` + état persistant | B4 tracking |
| **D6** | **Rituel** | Flag décoratif vs flux cast sans emplacement | Nouvelle commande / variante cast |
| **D7** | **`utility` + save** | Forcer `effect.type=saving_throw` quand save mécanique vs sous-objet `effect.save` | `entangle`, `faerie_fire` |
| **D8** | **Sorts de domaine clerc** | Restent hors fiche sort (`DOMAIN_SPELLS`) vs champ `granted_by_domain` | Préparés auto |
| **D9** | **i18n** | Conserver `{fr, en}` partout vs clé unique + table traduction | Compendium |
| **D10** | **Élargissement B3** | Ordre de priorité classes (mage 44 grimoire d'abord ?) vs transversal par niveau de sort | Planning contenu |

---

*Document généré — Lot B1. Aucun code de gameplay modifié.*
