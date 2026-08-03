# Préparation passe combat — arborescence et modélisation

> **Document de transmission** pour la session de conception Opus 5 (passe combat, lundi).  
> **Statut** : proposition de travail — rien n'est implémenté tant qu'une RFC / accord mainteneur ne l'a pas acté.  
> **Sources factuelles** : code au commit `main` post-lot DTO/API + client web ; `VISION.md` D3/D4 ; `ROADMAP.md` C0–C7 ; ADR-003.

---

## 1. Objectif de la passe

Livrer l'**ÉTAPE 4 — Système de combat** comme **API moteur pure** (VISION.md §5, ROADMAP C0–C7) :

- fonctions déterministes + événements publiés ;
- **aucun rendu** Discord, Web ni embed ;
- tests asserts sur état + événements.

Ce document pose **l'arborescence cible** et la **couche de modélisation personnages / effets** pour que la conception lundi parte du code réel, pas de suppositions.

---

## 2. État réel aujourd'hui (inventaire mesuré)

### 2.1 Personnage persisté

| Élément | Fichier | Rôle |
|---------|---------|------|
| `Character` | `jdr_engine/domain/character/character.py` | État persisté : identité, scores, `hp_current`/`hp_max`, `inventory`, `choices` |
| `CharacterSheet` | `jdr_engine/domain/character/character_sheet.py` | Vue dérivée, **jamais persistée** — calculée par `build_character_sheet()` |
| `choices` | `jdr_engine/domain/character/choices_schema.py` | Dict extensible normalisé à la sauvegarde |
| SQLite | `jdr_engine/persistence/database.py` | Table `personnages`, colonne `choices` JSON |

**Principe d'intégrité** (ROADMAP) : PV et emplacements sont **dérivés ou modifiés par le moteur** — jamais saisis librement. Seul chemin mécanique de modification PV joueur observé : **soins au cast** (`cast.py` → `_apply_healing()`). **Aucun chemin d'application de dégâts** sur un PJ.

### 2.2 Sous-états déjà dans `choices`

| Clé | Contenu | Usage combat potentiel |
|-----|---------|------------------------|
| `spellcasting` | emplacements, grimoire, **`concentration`** `{spell_id, spell_name}` | Concentration ✅ hors combat ; rupture dégâts ❌ |
| `feature_state` | rage, ki, second souffle, etc. | Compteurs classe — **dispersés**, pas un modèle effet |
| `rest` | dés de vie restants/total | Hors combat actif |

Accès feature : `jdr_engine/rules/class_features/common.py` (`feature_state()`, `set_feature_state()`).

### 2.3 Effets aujourd'hui

| Type | Mécanique | Display-only |
|------|-----------|--------------|
| Sort `healing` | Modifie `hp_current` | — |
| Sort `spell_attack` / `saving_throw` | Calcule `damage_total` dans `SpellCastResult` | **PV cible jamais touchés** |
| Sort `buff` / `utility` | `buff_text` / `utility_text` (YAML i18n) | ✅ |
| Concentration | Pose/remplacement/repos (`cast.py`, `state.py`) | Affichage fiche |
| Conditions SRD | **Aucune entrée compendium**, **aucun état perso** | Mentions ponctuelles d20 (`frightened`) |

Compendium sorts : 42 curated, schéma v2.0 — `EffectType` = `spell_attack | saving_throw | healing | buff | utility` (`jdr_engine/compendium/schemas/spell.py`). **13 sorts** `concentration: true`. Pas de champ structuré « condition appliquée » ni « durée en rounds ».

### 2.4 Placeholders combat

| Chemin | Contenu actuel |
|--------|----------------|
| `jdr_engine/game/` | `__init__.py` seul (commentaire Phase 7+) |
| `jdr_engine/core/events/` | `__init__.py` seul (commentaire Phase 6b+) |
| `data/combats/` | **Absent** (mentionné cible `ARCHITECTURE_TARGET.md`) |

### 2.5 Ce qui alimente déjà le combat futur

- `jdr_engine/dice/d20.py` — jets structurés, hooks features (rage, reckless, expertise…)
- `jdr_engine/rules/spellcasting/cast.py` — résolution sort mono-personnage
- `interfaces/discord/handlers/combat_roll.py` — flags `/roll` (affichage + hooks partiels)
- `docs/COMBAT_ROLL_PREREQUISITES.md` — prérequis flags, **documenté, non implémenté**

---

## 3. Principes de modélisation (décisions arrêtées à respecter)

| # | Principe | Source |
|---|----------|--------|
| P1 | **Combat = API moteur pure** — pas d'embed, pas de HTTP dans `jdr_engine/game/` | VISION D3 |
| P2 | **Le moteur ne connaît aucune interface** — publish events, jamais appeler Discord/Web | VISION D4, ADR-003 |
| P3 | **`Character` reste l'entité persistée du PJ** — le combat ne duplique pas une fiche complète | Code actuel |
| P4 | **Séparer état de rencontre vs état de personnage** — une rencontre référence des `character_id`, elle ne remplace pas `Character` | À acter lundi |
| P5 | **Effets = données structurées**, pas de texte pré-formaté dans le modèle combat | Aligné lot DTO/API |
| P6 | **Rule Engine calcule, Game Engine orchestre** — dégâts/touches = fonctions pures `rules/` ; tour, ordre, cibles = `game/` | ARCHITECTURE_TARGET §2 |
| P7 | **RFC avant implémentation ÉTAPE 4** — ce document prépare, n'autorise pas à coder sans accord | AGENTS.md §6 |

---

## 4. Arborescence proposée

Légende : ✅ existe · 🆕 à créer · 📝 placeholder actuel

```
jdr_engine/
├── domain/
│   ├── character/                    ✅ Character, CharacterSheet, choices_schema
│   ├── combat/                       🆕 Modèle de rencontre (voir §5)
│   │   ├── __init__.py
│   │   ├── combatant.py              🆕 Participant (PJ ou PNJ) dans une rencontre
│   │   ├── combat_state.py           🆕 État global rencontre (ordre, tour, round)
│   │   ├── action_economy.py         🆕 C4 — action / bonus / réaction / mouvement
│   │   └── identifiers.py            🆕 CombatantId, CombatId (NewType / str)
│   │
│   └── effects/                      🆕 Modèle d'effets actifs (voir §6)
│       ├── __init__.py
│       ├── active_effect.py          🆕 Effet structuré (source, cible, modificateurs, durée)
│       ├── condition.py              🆕 Condition SRD (id, durée, source)
│       ├── concentration.py          🆕 Extension combat (save CON, lien spell_id)
│       ├── modifiers.py              🆕 Bonus jets / dégâts / CA (ex. bless +1d4)
│       └── duration.py               🆕 Durée (rounds, concentration, until_rest…)
│
├── game/                             📝 → Game Engine combat
│   ├── __init__.py                   ✅ placeholder
│   ├── combat_manager.py             🆕 C1 — machine à états rencontre
│   ├── initiative.py                 🆕 C2 — jet, tri, ordre
│   ├── turn.py                       🆕 C4 — début/fin tour, économie d'actions
│   └── commands.py                   🆕 Commandes impératives (start, attack, end_turn…)
│
├── rules/
│   ├── combat/                       🆕 Fonctions pures SRD (Rule Engine)
│   │   ├── __init__.py
│   │   ├── damage.py                 🆕 apply_damage, apply_healing (généraliser cast)
│   │   ├── attack_resolution.py      🆕 C3 — jet vs CA, critique, auto-hit
│   │   ├── saving_throw.py           🆕 (ou réutiliser d20 + wrapper combat)
│   │   ├── concentration_save.py     🆕 C5 — save CON sur dégâts
│   │   └── conditions/               🆕 C6 — apply/remove, impact sur jets
│   │       ├── __init__.py
│   │       └── resolve.py
│   │
│   ├── effects/                      🆕 Pont compendium YAML → ActiveEffect
│   │   ├── __init__.py
│   │   ├── from_spell.py             🆕 buff YAML → modificateurs (B4)
│   │   └── registry.py               🆕 Catalogue effets mécaniques curated
│   │
│   ├── spellcasting/                 ✅ cast.py — à appeler depuis combat, pas dupliquer
│   ├── class_features/               ✅ feature_state — migrer progressivement vers effects?
│   └── calculator.py                 ✅ build_character_sheet — CA/PV de base
│
├── core/
│   └── events/                       📝 → EventBus (C0)
│       ├── __init__.py                 ✅ placeholder
│       ├── bus.py                    🆕 publish / subscribe synchrone
│       ├── domain_event.py           🆕 base DomainEvent (ADR-003)
│       └── combat_events.py          🆕 CombatStarted, DamageDealt, ConditionApplied…
│
├── application/
│   ├── character_service.py          ✅ inchangé hors combat
│   └── combat_service.py             🆕 C7 — use cases + persistance rencontre
│
└── persistence/
    ├── sqlite_character_repository.py ✅
    └── combat_repository.py          🆕 C7 — état rencontre (fichier ou table dédiée)

data/
└── combats/                          🆕 snapshots rencontre (cible ARCHITECTURE_TARGET)

tests/
├── unit/
│   ├── test_combat_state.py          🆕
│   ├── test_combat_damage.py         🆕
│   ├── test_active_effects.py        🆕
│   └── test_combat_events.py         🆕
└── integration/
    └── test_combat_flow.py           🆕 scénario minimal PJ vs PJ
```

**Hors périmètre moteur** (inchangé) :

```
interfaces/discord/     — s'abonnera plus tard aux événements
interfaces/api/         — banc test personnage ; combat API = lot ultérieur post-C7
bot/                    — maintenance, pas d'extension combat Discord (VISION D2)
```

---

## 5. Couche modélisation — personnages en combat

### 5.1 Deux niveaux d'état (distinction clé)

```
┌─────────────────────────────────────────────────────────────┐
│  Character (persisté, SQLite)                                │
│  — identité, level, ability_scores, choices, hp_current…     │
│  — source de vérité hors rencontre                           │
└───────────────────────────┬─────────────────────────────────┘
                            │ character_id
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Combatant (runtime, dans CombatState)                       │
│  — combatant_id, character_id | monster_id                   │
│  — hp_current_combat (peut diverger temporairement?)         │
│  — initiative_roll, initiative_order                           │
│  — active_effects: tuple[ActiveEffect, ...]                  │
│  — action_economy: ActionEconomy                             │
│  — flags tour (reckless_this_turn, etc.)                     │
└─────────────────────────────────────────────────────────────┘
```

**Question lundi** : en C1, le PV combat est-il une **copie** de `Character.hp_current` au début de rencontre, ou une **référence directe** (mutation du Character à chaque dégât) ?

Recommandation documentée pour Opus : **mutation du `Character` pour les PJ** (aligné persistance actuelle + auto-save C7), avec `CombatState` ne stockant que l'overlay rencontre (initiative, effets, économie d'actions).

### 5.2 `CombatState` (proposition de champs)

```python
# jdr_engine/domain/combat/combat_state.py — PROPOSITION, non implémenté

@dataclass
class CombatState:
    combat_id: str
    ruleset_id: str
    round_number: int                    # 1-based
    turn_index: int                      # index dans initiative_order
    initiative_order: tuple[str, ...]    # combatant_id ordonnés
    combatants: dict[str, Combatant]     # combatant_id → Combatant
    status: Literal["preparing", "active", "ended"]
    started_at: datetime | None
```

### 5.3 `Combatant` (proposition)

```python
@dataclass
class Combatant:
    combatant_id: str
    display_name: str
    kind: Literal["player_character", "npc", "monster"]
    character_id: str | None             # si PJ — lien vers Character persisté
    monster_id: str | None               # futur compendium monsters
    initiative: int | None               # total initiative (jet + mod)
    active_effects: tuple[ActiveEffect, ...]
    action_economy: ActionEconomy
    is_surprised: bool = False
    is_active: bool = True               # inconscient / mort / retiré
```

### 5.4 Cartographie `choices` existant → combat

| État actuel (`choices`) | Traitement proposé lundi |
|-------------------------|---------------------------|
| `spellcasting.concentration` | **Migrer conceptuellement** vers `ActiveEffect` type concentration, ou **wrapper** lisant l'existant jusqu'à B4 |
| `feature_state.rage_active` | **Court terme** : laisser dans `feature_state` ; **moyen terme** : `ActiveEffect` source `class_feature:rage` |
| `feature_state.reckless_active` | Flag **par tour** → plutôt sur `Combatant`, pas persisté entre sessions |
| `hp_current` / `hp_max` | Source PV ; `apply_damage()` dans `rules/combat/damage.py` |

### 5.5 PNJ / monstres

- Type `monster` mappé dans le compendium loader mais **aucune entrée** aujourd'hui.
- C1 peut démarrer avec **PJ vs PJ** ou **PJ vs Combatant statique** (CA/PV injectés) sans compendium monstre.

---

## 6. Couche modélisation — effets

### 6.1 Problème à résoudre

Aujourd'hui les « effets » sont :

1. **Texte YAML** (`buff_effect`) — non machine-readable ;
2. **Concentration** — dict minimal dans `choices.spellcasting` ;
3. **Feature state** — clés ad hoc par classe ;
4. **Résultat de cast** — `damage_total` sans application.

Le moteur combat a besoin d'un **modèle unique** pour : appliquer, expirer, modifier les jets, publier `ConditionApplied`.

### 6.2 `ActiveEffect` (proposition centrale)

```python
# jdr_engine/domain/effects/active_effect.py — PROPOSITION

EffectSourceKind = Literal[
    "spell",           # spell_id + slot level
    "class_feature",   # feature_id (rage, bless via domain…)
    "condition",       # condition_id SRD
    "racial_trait",
    "item",            # futur
]

@dataclass(frozen=True)
class EffectSource:
    kind: EffectSourceKind
    source_id: str                    # spell_id, feature_id, "frightened"…
    source_name: str | None = None    # libellé i18n cache optional

@dataclass(frozen=True)
class ActiveEffect:
    effect_id: str                    # uuid court, unique par instance
    source: EffectSource
    target_combatant_id: str
    applied_at_round: int | None      # None = hors combat / until_rest
    duration: EffectDuration          # voir §6.3
    modifiers: tuple[EffectModifier, ...]
    concentration: bool = False
    spell_id: str | None = None       # si concentration — lien cast existant
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 6.3 `EffectDuration` (proposition)

```python
DurationKind = Literal[
    "rounds",              # N rounds
    "concentration",       # jusqu'à rupture
    "until_end_of_turn",   # fin du tour actuel
    "until_start_of_turn", # début prochain tour cible
    "until_rest",          # repos court/long
    "permanent",           # rare — trait racial
]

@dataclass(frozen=True)
class EffectDuration:
    kind: DurationKind
    remaining_rounds: int | None = None
```

**Lien YAML** : `mechanics.duration` est aujourd'hui une **chaîne i18n** (« Concentration, jusqu'à 1 minute »). Une passe B4 devra définir un **mapping curated** spell_id → `EffectDuration` + `modifiers` pour les 7 buffs et 13 concentrations — **ne pas parser le texte FR**.

### 6.4 `EffectModifier` (proposition)

```python
ModifierKind = Literal[
    "attack_roll",         # +1d4 (bless)
    "saving_throw",
    "damage_roll",         # +1d6 (hex)
    "ac",
    "speed",
    "advantage_on",        # type de jet
    "disadvantage_on",
    "resistance",          # damage type
    "immunity",
]

@dataclass(frozen=True)
class EffectModifier:
    kind: ModifierKind
    value: int | str | None = None      # flat bonus ou damage type
    dice: str | None = None             # "1d4" pour bless
    scope: str | None = None            # ability, skill, damage_type…
```

### 6.5 Conditions (C6)

```python
# jdr_engine/domain/effects/condition.py — PROPOSITION

@dataclass(frozen=True)
class Condition:
    condition_id: str          # SRD : frightened, poisoned, prone…
    # Compendium entries/conditions/ — À CRÉER (manifest + YAML)
```

Impact sur jets : table SRD → hooks dans `rules/combat/conditions/resolve.py`, alimentant `D20RollRequest` (ex. `frightened` → désavantage attaques).

**État mesuré** : zéro entrée `conditions/` dans le compendium ; `manifest.yaml` ne déclare pas le type.

### 6.6 Concentration — double source à unifier

| Couche | Aujourd'hui | Cible combat |
|--------|-------------|--------------|
| Persistance PJ | `choices.spellcasting.concentration` | Conserver pour compat API/Discord |
| Runtime combat | — | `ActiveEffect(concentration=True)` + règle C5 save CON |

**Question lundi** : une seule fonction `set_concentration()` appelée par cast **et** par combat manager, ou synchronisation explicite combat → Character à la fin de rencontre ?

### 6.7 Registre effets sorts (pont B4 ↔ combat)

Fichier proposé : `jdr_engine/rules/effects/registry.py`

Contenu **curated** (comme les pools de sorts) — exemples prioritaires pour MVP combat :

| spell_id | effect.type YAML | Modificateurs proposés | Concentration |
|----------|------------------|------------------------|---------------|
| `bless` | buff | attack_roll +1d4, save +1d4 | non |
| `hex` | buff | damage_roll +1d6 vs cursed | oui |
| `haste` | buff | CA +2, action bonus, speed ×2 (partiel MVP) | oui |
| `hunters_mark` | buff | damage +1d6 | oui |
| `shield` | buff | AC +5 reaction (hors tour?) | non |

**7 buffs + 13 concentrations** dans le catalogue — le registre MVP n'a pas besoin de tout couvrir jour 1.

---

## 7. Flux de dégâts (lacune critique — C3)

Aujourd'hui **aucun** `apply_damage(character, amount)`.

Proposition de chaîne :

```
CombatManager.declare_attack(attacker_id, target_id, attack_spec)
  → rules/combat/attack_resolution.resolve(...)  → AttackResult
  → rules/combat/damage.apply_damage(target Character, amount, damage_type)
  → si target concentrateur : rules/combat/concentration_save.maybe_break(...)
  → publish(DamageDealt(...))
  → publish(ConditionApplied(...))  si effet secondaire
```

**Point d'ancrage unique** : `rules/combat/damage.py` — sort `spell_attack` devra **appeler la même fonction** lorsqu'une cible est identifiée (aujourd'hui cast sans cible).

---

## 8. Événements (C0 — ADR-003)

Base :

```python
@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    timestamp: datetime
    ruleset_id: str
    combat_id: str | None = None
```

Événements combat minimaux (C0–C3) :

| Événement | Payload minimal |
|-----------|-----------------|
| `CombatStarted` | combat_id, combatant_ids |
| `InitiativeRolled` | combatant_id, roll, total |
| `TurnStarted` | combatant_id, round |
| `AttackDeclared` | attacker_id, target_id |
| `AttackResolved` | hit: bool, roll, ac |
| `DamageDealt` | source_id, target_id, amount, damage_type, hp_after |
| `HealingApplied` | target_id, amount, hp_after |
| `ConcentrationBroken` | character_id, spell_id, reason |
| `ConditionApplied` | target_id, condition_id, source |
| `ConditionRemoved` | target_id, condition_id |
| `CombatEnded` | combat_id, reason |

Handlers futurs (hors moteur) : Discord embed, API WebSocket, `CombatAutoSaveHandler`.

---

## 9. Ordre de lots suggéré pour lundi (ROADMAP C0–C7)

| Ordre | Lot | Livrable testable | Dépend de |
|-------|-----|-------------------|-----------|
| 1 | **C0** | EventBus + `DomainEvent` + 1 test publish/subscribe | — |
| 2 | **C1** | `CombatState`, `Combatant`, `CombatManager.start/end` | C0 |
| 3 | **C3** (avant C2?) | `apply_damage`, `attack_resolution` sur 2 PJ | C1 |
| 4 | **C2** | Initiative jet + ordre + `TurnStarted` | C1 |
| 5 | **C5** | Concentration save CON sur dégâts | C3 + concentration existante |
| 6 | **C6** | 2–3 conditions (frightened, poisoned, prone) | C0 + compendium conditions |
| 7 | **C4** | Action economy basique | C2 |
| 8 | **C7** | `CombatService` + `combat_repository` | C1–C6 partiel |

**Note** : C3 avant C2 est discutable — l'important lundi est d'**ancrer `apply_damage`** tôt (prérequis C5 et sorts en combat).

Parallèle **B4** (effets mécaniques) : registre curated `bless`/`hex` minimum pour valider `ActiveEffect` + modifiers sur jets.

---

## 10. Non-objectifs explicites (lundi / première passe)

- Rendu Discord ou Web du combat
- Compendium monstres complet
- Armes/armures équipées → CA dynamique
- Validation flags `/roll` (`COMBAT_ROLL_PREREQUISITES.md`) — lot séparé
- Multi-rooms / concurrence combats (dernier écrivain gagne, comme SQLite actuel)
- Portage règles 2024

---

## 11. Dettes et bugs connus à ne pas aggraver

| Item | Fichier / note |
|------|----------------|
| `CharacterSheet.trait_ids` contient des libellés, pas des ids | ROADMAP backlog |
| Compteurs ressources (rage, ki…) non structurés dans DTO | `output_serializers.py` docstring |
| `buff_text` seul pour 7 sorts buff | B4 |
| Sorts calculent dégâts sans cible | `cast.py` |
| `interfaces/api/` = personnage seulement, pas combat | Lot ultérieur |

---

## 12. Documents canoniques à lire avant la session

| Document | Pourquoi |
|----------|----------|
| `VISION.md` §5, §9, §10 | D3 combat API pure, ordre moteur → Web |
| `ROADMAP.md` C0–C7, B4 | Lots et statuts |
| `docs/adr/ADR-003` | EventBus |
| `docs/COMBAT_ROLL_PREREQUISITES.md` | Flags existants Discord |
| `jdr_engine/rules/spellcasting/cast.py` | Cast actuel, `_apply_healing` |
| `jdr_engine/application/dto/output_serializers.py` | Principe données-only |
| `docs/SPELL_SCHEMA.md` | Types d'effets YAML |

---

## 13. Questions ouvertes pour Opus 5 (lundi)

1. **PV combat** : mutation directe de `Character` vs copie overlay ?
2. **Concentration** : unifier `choices.spellcasting.concentration` et `ActiveEffect` comment ?
3. **C1 scope** : PJ-only suffisant pour MVP, ou Combatant statique dès jour 1 ?
4. **Conditions** : créer `compendium/dnd5e/entries/conditions/` maintenant ou enum SRD en dur phase 1 ?
5. **feature_state** : migrer vers `ActiveEffect` dans C1 ou reporter post-MVP ?
6. **Persistance combat** : table SQLite `combats` vs fichiers `data/combats/` ?
7. **RFC** : format attendu (ADR séparé combat vs extension ADR-003) ?

---

*Généré pour transmission Opus 5 — base de conception, pas d'implémentation sans accord mainteneur.*
