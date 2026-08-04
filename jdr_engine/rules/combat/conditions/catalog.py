# jdr_engine/rules/combat/conditions/catalog.py
"""Conditions SRD phase 1 — enum en dur (ADR-004 décision 4, lot C6)."""
from __future__ import annotations

PHASE1_CONDITIONS: frozenset[str] = frozenset({"frightened", "poisoned"})


class UnknownCombatConditionError(Exception):
    """Condition demandée hors périmètre phase 1."""


def validate_phase1_condition(condition_id: str) -> str:
    """Valide et retourne l'id de condition phase 1."""
    normalized = str(condition_id).strip()
    if normalized not in PHASE1_CONDITIONS:
        raise UnknownCombatConditionError(
            f"Condition {condition_id!r} hors périmètre phase 1 C6 "
            f"({sorted(PHASE1_CONDITIONS)})."
        )
    return normalized
