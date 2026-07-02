# ADR-003 — Pourquoi utiliser un EventBus

| Attribut | Valeur |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-07-02 |
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
| | Overkill pour un bot Discord JDR |

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
- Tests : `events = bus.capture()` → assert `AttackResolved` publié
- Logger/audit gratuit via handler dédié
- Auto-save combat via handler persistence

### Négatives / garde-fous

| Risque | Mitigation |
|---|---|
| Handler lent bloque le flux | Timeout par handler ; exécution async optionnelle |
| Handler qui lève une exception | Wrapper : log + continue (ne pas crasher le moteur) |
| Ordre des handlers non garanti | Documenter ; handlers indépendants les uns des autres |
| Debugging « qui a réagi ? » | `EventBusRegistry.debug_handlers()` + log structuré |
| Over-publishing | Publier uniquement des **Domain Events** significatifs, pas chaque getter |

### Ce que l'EventBus n'est PAS

- **Pas** un remplacement de la couche Application (les services restent)
- **Pas** un mécanisme de règles (les calculs restent dans Rule Engine)
- **Pas** de la persistance automatique (un handler dédié décide quoi sauver)

---

## Références

- ADR-001 — Rule Engine
- `docs/ARCHITECTURE_V2.md` — Sections EventBus, Plugins, Interfaces
