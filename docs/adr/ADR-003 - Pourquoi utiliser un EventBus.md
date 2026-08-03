# ADR-003 — Pourquoi utiliser un EventBus

| Attribut | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-07-02 |
| **Complément lot C0** | 2026-08-03 |
| **Décideurs** | Lead Architect, Product Owner |
| **Contexte** | Découplage Game Engine / Interfaces / extensions futures |

---

## Contexte

Le moteur JDR va émettre de nombreux **événements métier** au fil du jeu :

- `CharacterCreated`, `CharacterLevelUp`
- `CombatStarted`, `InitiativeRolled`, `TurnStarted`
- `AttackDeclared`, `DamageDealt`, `HealingApplied`
- `ConditionApplied`, `ConditionRemoved`
- `ItemEquipped`, `ItemLooted`
- `QuestStarted`, `QuestCompleted`
- `SpellCast`, `SpellSlotConsumed`

**Consommateurs potentiels** de ces événements :

| Consommateur | Besoin |
|---|---|
| **Discord Adapter** | Mettre à jour embeds, envoyer messages canal |
| **API REST** (futur) | WebSocket push vers clients Web |
| **Logger / Audit** | Traçabilité des actions en session |
| **Plugins** | Réactions custom (musique, achievements…) |
| **Persistence** | Sauvegarde réactive (auto-save combat) |
| **Analytics** (futur) | Statistiques de campagne |
| **Foundry VTT** (futur) | Sync état vers tokens |

Si le Game Engine appelle directement Discord (`await channel.send(...)`) ou si chaque consommateur est injecté en dur dans les services, le couplage explose et **chaque nouvelle interface = modification du moteur**.

---

## Décision

Nous introduisons un **EventBus** (pub/sub in-process) dans `jdr_engine/core/events/`.

### Contrat

```python
# Conceptuel

@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    timestamp: datetime
    ruleset_id: str
    session_id: str | None

class EventBus(Protocol):
    def publish(self, event: DomainEvent) -> None: ...
    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None: ...
    def unsubscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None: ...
```

### Règles

1. Le **Game Engine** et les **Application Services** **publient** des événements — ils ne connaissent **aucun** abonné
2. Les **Interfaces** (Discord, API) **s'abonnent** et traduisent en actions UI
3. Les **Plugins** s'enregistrent comme handlers via le système d'extensions
4. Les événements sont **immutables** (`frozen dataclass`)
5. Le bus est **synchrone in-process** en v1 ; interface compatible avec un bus async/message queue en v2 si besoin scale
6. **Aucune dépendance Discord** dans les événements du domaine
7. **Correspondance de type exacte** : un abonné enregistré pour `T` reçoit uniquement les événements dont `type(event) is T` — pas de remontée d'héritage (voir § Clôture lot C0)
8. **Événements plats** : chaque événement métier est une sous-classe **directe** de `DomainEvent`, sans classe intermédiaire porteuse de sémantique (ex. pas de `CombatEvent` parent) — lots C1–C7

### Exemple de flux

```
CombatService.attack(cmd)
  → CombatManager.resolve_attack()
  → publish(AttackResolved(attacker, target, roll, damage))
      → DiscordCombatHandler → edit embed + message canal
      → CombatAutoSaveHandler → persistence.save(combat)
      → AuditLogHandler → log fichier
      → [Plugin] CriticalHitSoundHandler → (no-op si pas Discord)
```

---

## Alternatives envisagées

### Alternative A — Appels directs (couplage fort)

```python
class CombatService:
    def __init__(self, discord_notifier, webhook, logger):
        ...
    def attack(self, cmd):
        result = self.manager.resolve(cmd)
        self.discord_notifier.notify(result)
        self.logger.log(result)
```

| Pour | Contre |
|---|---|
| Simple, explicite | Chaque consommateur = paramètre du constructeur |
| Facile à debugger | Game Engine connaît Discord |
| | Ajout Web/API = modifier CombatService |
| | Tests require mocks de tous les consommateurs |

**Rejetée** — viole l'indépendance des interfaces.

### Alternative B — Hooks / callbacks enregistrés manuellement

```python
combat_service.on_attack(callback)
```

| Pour | Contre |
|---|---|
| Découplage partiel | Pas de standard, liste de callbacks à maintenir |
| | Ordre d'exécution flou |
| | Pas de typage fort des événements |

**Rejetée** — EventBus typé est strictement supérieur.

### Alternative C — Event Sourcing complet

L'état du jeu = replay de tous les événements depuis le début.

| Pour | Contre |
|---|---|
| Audit trail parfait | Complexité extrême |
| Time travel | Rebuild d'état coûteux |
| | Overkill pour le client Discord de JDR Engine |

**Rejetée pour l'instant** — le bus publish/subscribe suffit ; certains événements peuvent être **persistés** sélectivement (log de combat) sans event sourcing global.

### Alternative D — EventBus in-process typé (choix retenu)

| Pour | Contre |
|---|---|
| Découplage total moteur ↔ interfaces | Handlers mal écrits peuvent ralentir le flux |
| Typage fort (dataclass par event) | Debugging indirect (qui écoute quoi ?) |
| Extensible (plugins = handlers) | Risque de handlers circulaires si mal conçu |
| Testable (assert events published) | |
| Migration future vers Redis/NATS possible | |

**Retenue.**

### Alternative E — Message broker externe (Redis, RabbitMQ)

| Pour | Contre |
|---|---|
| Multi-process, distribué | Infrastructure supplémentaire |
| Scale horizontal | Overkill phase 1 |
| | Latence réseau pour chaque action |

**Rejetée pour v1** — interface du bus conçue pour permettre un **adapter** Redis plus tard sans changer le Game Engine.

---

## Conséquences

### Positives

- Discord, Web, CLI coexistent sans modifier le moteur
- Plugins = handlers enregistrés au boot
- Tests : handlers manuels enregistrés sur le bus → assert contenu reçu (pas de mécanisme `capture()` dédié)
- Logger/audit gratuit via handler dédié
- Auto-save combat via handler persistence
- Diagnostic dev (lot C0) : tampon mémoire + page `/debug/events/view` (voir commit C0 API)

### Négatives / garde-fous

| Risque | Mitigation |
|---|---|
| Handler lent bloque le flux | Bus synchrone : pas de timeout possible sans interrompre la pile appelante — **hors scope v1** ; handlers doivent rester légers |
| Handler qui lève une exception | Wrapper : log + continue (ne pas crasher le moteur) — **implémenté lot C0** |
| Ordre des handlers | **Déterministe** : ordre d'enregistrement garanti (lot C0) ; handlers indépendants les uns des autres |
| Debugging « qui a réagi ? » | Page diagnostic API (lot C0) ; pas de `EventBusRegistry.debug_handlers()` |
| Over-publishing | Publier uniquement des **Domain Events** significatifs, pas chaque getter |
| Récursion mutuelle entre effets (publication réentrante) | Compteur de profondeur avec plafond — **dette lot C6** (effets en cascade) ; non implémenté en C0 |

### Ce que l'EventBus n'est PAS

- **Pas** un remplacement de la couche Application (les services restent)
- **Pas** un mécanisme de règles (les calculs restent dans Rule Engine)
- **Pas** de la persistance automatique (un handler dédié décide quoi sauver)

---

## Clôture lot C0 (2026-08-03)

Document de référence implémentation : `jdr_engine/core/events/` (bus + tests), diagnostic API `interfaces/api/diagnostic/`.

### Correspondance de type exacte — décision d'architecture

La livraison par **`type(event)` strict** (égalité de type, sans remontée MRO) est **actée**, pas un détail d'implémentation jetable.

| Pour | Contre |
|---|---|
| Traçabilité : on sait exactement qui reçoit quoi | Abonnement « famille » = plusieurs `subscribe` explicites |
| Passage ultérieur au polymorphisme = changement **localisé au bus** et à ses tests | Commodité d'un handler sur une super-classe absente en v1 |
| Retrait d'une hiérarchie d'événements déjà répandue dans le moteur serait **non local** | |

**Voie de sortie** si le besoin apparaît : remontée de la chaîne d'héritage (`MRO`) lors de la livraison — changement circonscrit à `EventBus.publish` et à `test_event_bus.py`.

### Événements plats — contrainte lots C1–C7

Les événements de combat (`CombatStarted`, `DamageDealt`, `ConcentrationBroken`, etc.) **héritent directement** de `DomainEvent`. **Aucune** classe intermédiaire (`CombatEvent`, `CombatDomainEvent`, …) ne porte de champs ou sémantique partagée.

Le besoin d'écouter plusieurs types (ex. audit de toute action de combat) se satisfait par **plusieurs abonnements explicites** — un handler par type, ou un handler unique enregistré plusieurs fois via lambdas/wrappers si la logique est commune.

Champs contextuels (`combat_id`, etc.) vivent sur **chaque** sous-classe qui en a besoin, pas sur un ancêtre intermédiaire.

### Points écartés définitivement

| Point | Statut | Raison |
|---|---|---|
| **Timeout par handler** | **Clos — non applicable** | Sur un bus synchrone in-process, un timeout impliquerait d'interrompre du code s'exécutant dans la pile de l'appelant |
| **`debug_handlers()` / `EventBusRegistry`** | **Clos — remplacé** | Page diagnostic C0 (`GET /debug/events`, `/debug/events/view`) |
| **`bus.capture()` pour les tests** | **Clos — superflu** | Handlers manuels dans les tests unitaires plus lisibles qu'un mécanisme dédié |

### Choix d'implémentation retenus (lot C0)

| Choix | Détail |
|---|---|
| **Classe concrète `EventBus`** | Plutôt que `Protocol` seul — cohérent avec un bus in-process unique ; un adapter externe (Redis) reste une façade distincte |
| **Réentrance autorisée** | Livraison **depth-first immédiate** : un `publish` imbriqué est intégralement livré avant de reprendre les abonnés restants de l'événement parent |
| **Snapshot des abonnés** | Liste copiée au début de chaque `publish` — `subscribe` / `unsubscribe` pendant une livraison n'affecte pas la livraison en cours |

Sémantique documentée dans `jdr_engine/core/events/bus.py`.

### Dette assumée — plafond de profondeur réentrante

La réentrance depth-first expose un risque de **récursion mutuelle** entre effets (A publie B, B publie A…) lorsque les effets en cascade seront branchés.

Un **compteur de profondeur avec plafond** sera nécessaire au lot introduisant ces cascades — **C6** selon l'ordonnancement ADR-004. **Non implémenté en C0** : sans effets réels, le plafond serait arbitraire.

---

## Références

- ADR-001 — Rule Engine
- [ADR-004](ADR-004-modele-combat.md) — Modèle de combat (événements plats, payloads combat)
- `jdr_engine/core/events/` — Implémentation lot C0
- `docs/ARCHITECTURE_TARGET.md` — Sections EventBus, Plugins, Interfaces
