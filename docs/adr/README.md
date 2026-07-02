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

## Documents associés

- [ARCHITECTURE_V2.md](../ARCHITECTURE_V2.md) — Architecture cible complète

## Règle

> Toute décision structurelle importante qui n'est pas évidente au premier coup d'œil **doit** produire un ADR avant implémentation.

### ADRs futurs prévus

- ADR-004 — Structure du Compendium (dossier par entité)
- ADR-005 — Stratégie i18n (fichiers par locale)
- ADR-006 — Validation Compendium (strict vs warn)
- ADR-007 — Versionnement des rulesets
- ADR-008 — Système de plugins (sandbox)
