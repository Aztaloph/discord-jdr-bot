# Architecture Decision Records (ADR)

Ce dossier contient les **décisions d'architecture** du projet moteur JDR.

## Format

Chaque ADR documente :

- **Contexte** — pourquoi la question s'est posée
- **Décision** — ce qui a été choisi
- **Alternatives** — ce qui a été envisagé et rejeté
- **Conséquences** — impacts positifs et négatifs

## Index

| ADR | Titre | Statut |
|---|---|---|
| [ADR-001](ADR-001%20-%20Pourquoi%20un%20Rule%20Engine.md) | Pourquoi un Rule Engine | Accepté |
| [ADR-002](ADR-002%20-%20Pourquoi%20les%20règles%20sont%20externalisées.md) | Pourquoi les règles sont externalisées | Accepté |
| [ADR-003](ADR-003%20-%20Pourquoi%20utiliser%20un%20EventBus.md) | Pourquoi utiliser un EventBus | Accepté |
| [ADR-004](ADR-004-modele-combat.md) | Modèle de combat | Accepté |
| [ADR-005](ADR-005-transition-fin-rencontre.md) | Transition fin de rencontre | Accepté |

## Documents associés

- [ARCHITECTURE.md](../ARCHITECTURE.md) — État actuel du dépôt
- [ARCHITECTURE_TARGET.md](../ARCHITECTURE_TARGET.md) — Architecture cible complète

## Règle

> Toute décision structurelle importante qui n'est pas évidente au premier coup d'œil **doit** produire un ADR avant implémentation.

### ADRs futurs prévus

- ADR-010 — Structure du Compendium (dossier par entité)
- ADR-006 — Stratégie i18n (fichiers par locale)
- ADR-007 — Validation Compendium (strict vs warn)
- ADR-008 — Versionnement des rulesets
- ADR-009 — Système de plugins (sandbox)
