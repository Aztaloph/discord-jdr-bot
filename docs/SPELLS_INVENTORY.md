# Inventaire des sorts — Lot B1 (état au 24 juillet 2026)

> **Périmètre** : recensement exhaustif du catalogue **curated** actuel (28 sorts uniques).  
> Aucun nouveau sort, aucune modification de gameplay dans ce lot.

---

## 1. Où sont stockées les définitions ?

| Couche | Fichier / dossier | Rôle |
|---|---|---|
| **Source de vérité (contenu)** | `compendium/dnd5e/entries/spells/<id>/definition.yaml` | Définition YAML par sort (1 dossier = 1 sort) |
| **Schéma typé (validation)** | `jdr_engine/compendium/schemas/spell.py` | Modèle Pydantic `SpellMechanics`, `CantripScaling`, `SlotScaling`, `SpellComponents` |
| **Chargement runtime** | `jdr_engine/compendium/loader.py` → `RuleEngine.get_entity("spell", id)` | Entrée compendium indexée par `id` |
| **Pools par classe (curated)** | `jdr_engine/rules/spellcasting/spells_catalog.py` | Listes `*_CANTRIP_IDS`, `*_SPELL_IDS`, `WIZARD_SPELLBOOK_POOL`, etc. |
| **Quotas SRD (niv. perso)** | `jdr_engine/rules/spellcasting/model.py` | `cantrips_known_capacity`, `spellbook_capacity`, `prepared_capacity_for_class` |
| **Montée de niveau / rebuild** | `jdr_engine/rules/spellcasting/preparation.py` | `upgrade_*_spellcasting` — remplit cantrips / grimoire / connus depuis le **pool curated** |
| **Lancement** | `jdr_engine/rules/spellcasting/cast.py` | Lit `mechanics` + `effect` depuis le compendium |
| **Affichage embed** | `jdr_engine/rules/spellcasting/mechanics_display.py` | Référence mécanique (DD, scaling, composantes) |

**Relation quota ↔ catalogue** : à la montée de niveau, le moteur calcule  
`len(liste) = min(quota_SRD(niv.), len(pool_curated_classe))`.  
Voir test `test_curated_pool_caps_spellbook_and_cantrips_before_srd_quota` (`tests/unit/test_level_up_full_caster_a2.py`).

---

## 2. Pools magicien (référence explicite)

| Pool | IDs (8 + 4) |
|---|---|
| **WIZARD_CANTRIP_IDS** (4) | `fire_bolt`, `mage_hand`, `light`, `ray_of_frost` |
| **WIZARD_SPELLBOOK_POOL** (18) | niv. 1–2 : `mage_armor` … `flaming_sphere` ; niv. 3 (B3-a) : `fireball` … `haste` ; niv. 4 (B3-b) : `polymorph`, `banishment`, `dimension_door`, `ice_storm` |

Quota SRD grimoire niv. 20 = **44** ; pool curated = **18** → plafond effectif **18**.

---

## 3. Pools par classe (tous lanceurs)

| Classe | Cantrips (n) | Sorts niv. 1+ (n) | Remarque |
|---|---:|---:|---|
| **wizard** | 4 | 18 (grimoire) | Hybrid ; pool SRD B2-ter + B3-a + B3-b |
| **sorcerer** | 5 | 7 (connus) | `hellish_rebuke` en plus du pool mage partiel |
| **cleric** | 3 | 5 | + sorts de domaine (`life`) hors quota |
| **druid** | 3 | 4 | |
| **bard** | 2 | 6 | `BARD_SPELL_IDS` inclut cantrips + sorts |
| **warlock** | 2 | 3 | Pact Magic (hors axe A/B actuel) |
| **ranger** | — | 3 | Demi-lanceur |
| **paladin** | — | 3 | Demi-lanceur |

**Total sorts uniques dans le compendium** : **42** (= union de tous les pools, sans doublon).

---

## 4. Table maîtresse — 28 sorts

Légende colonnes **Champs** :
- ✅ présent et renseigné (non null / non vide)
- ⬜ clé absente ou explicitement `null`
- ⚠️ présent mais **non consommé** par le moteur de cast aujourd'hui

| id | Nom (FR) | Niv. | École | Classes (pools) | `effect.type` | Conc. | Rituel | cantrip_scaling | slot_scaling | save (méca.) |
|---|---|---:|---|---|---|:---:|:---:|---|---|---|
| `fire_bolt` | Trait de feu | 0 | évocation | mage, ensorceleur | spell_attack | ⬜ | ⬜ | ✅ | ⬜ | ⬜ |
| `thaumaturgy` | Thaumaturgie | 0 | transmutation | mage, ensorceleur, clerc, barde | utility | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| `guidance` | Guidance | 0 | divination | ensorceleur, clerc, druide | buff | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| `vicious_mockery` | Moquerie cruelle | 0 | enchantement | mage, ensorceleur, barde | saving_throw | ⬜ | ⬜ | ✅ | ⬜ | WIS |
| `sacred_flame` | Flamme sacrée | 0 | évocation | ensorceleur, clerc | saving_throw | ⬜ | ⬜ | ✅ | ⬜ | DEX |
| `produce_flame` | Flamme vivante | 0 | conjuration | druide | spell_attack | ⬜ | ⬜ | ✅ | ⬜ | ⬜ |
| `druidcraft` | Artisanat druidique | 0 | transmutation | druide | utility | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| `eldritch_blast` | Salve occulte | 0 | évocation | occultiste | spell_attack | ⬜ | ⬜ | ✅ | ⬜ | ⬜ |
| `prestidigitation` | Prestidigitation | 0 | transmutation | occultiste | utility | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| `chromatic_orb` | Orbe chromatique | 1 | évocation | mage, ensorceleur | spell_attack | ⬜ | ⬜ | ⬜ | ✅ | ⬜ |
| `burning_hands` | Mains brûlantes | 1 | évocation | mage, ensorceleur | saving_throw | ⬜ | ⬜ | ⬜ | ✅ | DEX |
| `detect_magic` | Détection de la magie | 1 | divination | mage, ensorceleur, clerc, barde, rôdeur, paladin | utility | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| `magic_missile` | Projectile magique | 1 | évocation | mage, ensorceleur | spell_attack | ⬜ | ⬜ | ⬜ | ✅ | ⬜ |
| `shield` | Bouclier | 1 | abjuration | mage, ensorceleur | buff | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| `cure_wounds` | Soins | 1 | évocation | clerc, barde, rôdeur, paladin, druide | healing | ⬜ | ⬜ | ⬜ | ✅ | ⬜ |
| `bless` | Bénédiction | 1 | enchantement | clerc, barde, paladin | buff | ✅ | ⬜ | ⬜ | ✅ | ⬜ |
| `inflict_wounds` | Blessure | 1 | nécromancie | clerc | spell_attack | ⬜ | ⬜ | ⬜ | ✅ | ⬜ |
| `healing_word` | Mot de guérison | 1 | évocation | barde | healing | ⬜ | ⬜ | ⬜ | ✅ | ⬜ |
| `hellish_rebuke` | Réprimande infernale | 1 | évocation | ensorceleur | saving_throw | ⬜ | ⬜ | ⬜ | ✅ | DEX |
| `entangle` | Enchevêtrement | 1 | conjuration | druide | utility | ✅ | ⬜ | ⬜ | ⬜ | STR ⚠️ |
| `faerie_fire` | Lueurs féeriques | 1 | évocation | druide | utility | ✅ | ⬜ | ⬜ | ⬜ | DEX ⚠️ |
| `hunters_mark` | Marque du chasseur | 1 | divination | rôdeur | buff | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| `hex` | Maléfice | 1 | enchantement | occultiste | utility | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| `armor_of_agathys` | Armure d'Agathys | 1 | abjuration | occultiste | utility | ⬜ | ⬜ | ⬜ | ✅ | ⬜ |
| `scorching_ray` | Rayon ardent | 2 | évocation | mage, ensorceleur | spell_attack | ⬜ | ⬜ | ⬜ | ✅ | ⬜ |
| `darkness` | Ténèbres | 2 | évocation | mage, occultiste | utility | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| `spiritual_weapon` | Arme spirituelle | 2 | évocation | clerc | spell_attack | ⬜ | ⬜ | ⬜ | ✅ | ⬜ |
| `flaming_sphere` | Sphère enflammée | 2 | conjuration | mage, druide | saving_throw | ✅ | ⬜ | ⬜ | ✅ | DEX |

\* B2-bis : `guidance` retiré du pool mage ; reste ensorceleur/clerc/druid (hors SRD ensorceleur — arbitrage B3).

---

## 5. Champs YAML — présents vs absents (modèle actuel)

### 5.1 En-tête (tous les sorts)

| Champ | Présent | Notes |
|---|---|---|
| `schema_version` | ✅ 28/28 | Toujours `"1.0"` |
| `type` | ✅ 28/28 | Toujours `spell` |
| `id` | ✅ 28/28 | = nom du dossier |
| `name.fr` / `name.en` | ✅ 28/28 | Localisé |

### 5.2 Bloc `mechanics` (schéma `SpellMechanics`)

| Champ | Présence | Consommé par le moteur ? |
|---|---|---|
| `level` | ✅ 28/28 | **Oui** — niveau de sort, cantrip = 0 (`cast.py`, slots, pools filtrés) |
| `school` | ✅ 28/28 | **Affichage** — embed référence |
| `casting_time` | ✅ 28/28 | **Affichage** |
| `range` | ✅ 28/28 | **Affichage** |
| `components` (V/S/M) | ✅ 28/28 | **Affichage** (`format_spell_components`) |
| `duration` | ✅ 28/28 | **Affichage** |
| `concentration` | ✅ 28/28 | **Partiel** — affiché ; pas de tracking persistant en jeu |
| `ritual` | ⬜ 27/28 | Seul `detect_magic` = `true` ; **non exploité** en cast |
| `attack_roll` | ✅ 28/28 | **Affichage** + heuristique auto-hit (`magic_missile`) |
| `damage_dice` | ⚠️ 18/28 | **Affichage** ; cast utilise surtout `effect.damage` |
| `damage_type` | ⚠️ 18/28 | **Affichage** + cast |
| `save` | ⬜ 22/28 | **Affichage** ; cast lit `effect.ability` pour saving_throw |
| `description` | ✅ 28/28 | **Affichage** |
| `cantrip_scaling` | ✅ 6/28 | **Oui** — `resolve_cantrip_scaling_tier` (dégâts cantrip) |
| `slot_scaling` | ✅ 14/28 | **Partiel** — missiles `scorching_ray` oui ; +d8/`spiritual_weapon` **non** |
| `effect` | ✅ 28/28 | **Oui** — branche principale du cast |
| `buff_effect` | ⬜ 22/28 | **Affichage** (texte embed) |
| `utility_effect` | ⬜ 18/28 | **Affichage** |
| `invocation_effect` | ⬜ 27/28 | Seul `spiritual_weapon` ; affichage clerc domaine |

### 5.3 Sous-champs `effect` (par `effect.type`)

| `effect.type` | Sorts (n) | Champs typiquement présents | Manques fréquents |
|---|---:|---|---|
| `spell_attack` | 10 | `damage`, `damage_type`, parfois `attacks`, `attack_type` | `auto_hit` (sauf `magic_missile`) |
| `saving_throw` | 5 | `damage`, `ability`, `half_on_save` | — |
| `healing` | 2 | `healing`, `add_ability_mod` | — |
| `buff` | 4 | (souvent vide — texte dans `buff_effect`) | effet mécanique structuré |
| `utility` | 7 | (souvent vide — texte dans `utility_effect`) | save parfois seulement dans `mechanics.save` |

---

## 6. Répartition par niveau de sort

| Niv. | Nombre | IDs |
|---:|---:|---|
| 0 (cantrip) | 9 | fire_bolt, thaumaturgy, guidance, vicious_mockery, sacred_flame, produce_flame, druidcraft, eldritch_blast, prestidigitation |
| 1 | 15 | chromatic_orb, burning_hands, detect_magic, magic_missile, shield, cure_wounds, bless, inflict_wounds, healing_word, hellish_rebuke, entangle, faerie_fire, hunters_mark, hex, armor_of_agathys |
| 2 | 4 | scorching_ray, darkness, spiritual_weapon, flaming_sphere |

Aucun sort niv. 3–9 dans le catalogue curated actuel.

---

## 7. Écarts connus (dette B2–B4)

1. **`slot_scaling` métadonnées vs calcul** — présent sur 14 sorts ; seul le bonus de rayons (`missiles`) est appliqué au cast pour `scorching_ray`.
2. **Concentration** — booléen présent, état `choices.spellcasting.concentration` non posé pour la plupart des `utility`.
3. **Saves « décoratifs »** — `entangle`, `faerie_fire` : `mechanics.save` renseigné mais `effect.type = utility` → pas de jet au cast.
4. **Classes** — non stockées dans le YAML ; uniquement dans `spells_catalog.py`.
5. **Pool vs SRD** — quotas niv. 6–20 dépassent le catalogue (A2 validé) ; élargissement = axe B3.

---

*Document généré — Lot B1. Prochaine étape : `docs/SPELL_SCHEMA.md` + implémentation B2.*
