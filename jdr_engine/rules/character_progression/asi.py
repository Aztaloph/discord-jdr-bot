# jdr_engine/rules/character_progression/asi.py
"""Amélioration de caractéristiques (ASI) — SRD 2014."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import (
    DEFAULT_ABILITY_IDS,
    AbilityScores,
)
from jdr_engine.domain.character.effective_scores import compute_effective_ability_scores

ASI_LEVELS: frozenset[int] = frozenset({4, 8, 12, 16, 19})
ASI_POINT_BUDGET = 2
MAX_ABILITY_SCORE = 20

ABILITY_LABELS_FR: dict[str, str] = {
    "str": "Force",
    "dex": "Dextérité",
    "con": "Constitution",
    "int": "Intelligence",
    "wis": "Sagesse",
    "cha": "Charisme",
}


class AsiValidationError(ValueError):
    """Choix ASI invalide (format, cap 20, carac. identiques)."""


def requires_asi_at_level(level: int) -> bool:
    return level in ASI_LEVELS


def asi_points_remaining(pending: dict[str, int]) -> int:
    """Points ASI non dépensés (budget 2)."""
    spent = sum(int(value) for value in pending.values() if value)
    return ASI_POINT_BUDGET - spent


def can_increase_asi(
    base_scores: dict[str, int],
    racial_bonuses: dict[str, int],
    pending: dict[str, int],
    ability_id: str,
) -> bool:
    """True si +1 sur ``ability_id`` respecte budget et cap effectif ≤ 20."""
    if ability_id not in DEFAULT_ABILITY_IDS:
        return False
    if asi_points_remaining(pending) <= 0:
        return False
    base = dict.fromkeys(DEFAULT_ABILITY_IDS, 10)
    base.update(base_scores)
    pending_on_stat = int(pending.get(ability_id, 0))
    new_base = base[ability_id] + pending_on_stat + 1
    new_effective = new_base + racial_bonuses.get(ability_id, 0)
    return new_effective <= MAX_ABILITY_SCORE


def can_decrease_asi(pending: dict[str, int], ability_id: str) -> bool:
    """True si un +ASI en cours peut être retiré sur cette carac."""
    return int(pending.get(ability_id, 0)) > 0


def is_asi_pending_complete(pending: dict[str, int]) -> bool:
    """True si exactement 2 points ASI sont répartis (prêt pour Confirmer)."""
    return sum(int(value) for value in pending.values() if value) == ASI_POINT_BUDGET


def _effective_scores(
    base_scores: dict[str, int],
    racial_bonuses: dict[str, int],
) -> dict[str, int]:
    base = dict.fromkeys(DEFAULT_ABILITY_IDS, 10)
    base.update(base_scores)
    return compute_effective_ability_scores(base, racial_bonuses)


def validate_asi(
    base_scores: dict[str, int],
    racial_bonuses: dict[str, int],
    choice: dict[str, int],
) -> dict[str, int]:
    """
    Valide un ASI : +2 à une carac OU +1/+1 à deux caracs distinctes.

    Le cap SRD 20 s'applique au score **effectif** (base + racial).
    Retourne les bonus normalisés à appliquer sur la **base** uniquement.
    """
    if not choice:
        raise AsiValidationError("Aucun bonus ASI fourni.")

    bonuses: dict[str, int] = {}
    for raw_id, raw_delta in choice.items():
        ability_id = str(raw_id).strip().lower()
        if ability_id not in DEFAULT_ABILITY_IDS:
            raise AsiValidationError(f"Caractéristique inconnue : {raw_id!r}.")
        try:
            delta = int(raw_delta)
        except (TypeError, ValueError) as exc:
            raise AsiValidationError(f"Bonus invalide pour {ability_id!r}.") from exc
        if delta <= 0:
            raise AsiValidationError("Les bonus ASI doivent être positifs.")
        bonuses[ability_id] = bonuses.get(ability_id, 0) + delta

    total = sum(bonuses.values())
    if total != 2:
        raise AsiValidationError(
            "Un ASI doit représenter exactement **+2** points "
            f"(reçu : {total})."
        )

    if len(bonuses) == 1:
        ability_id, delta = next(iter(bonuses.items()))
        if delta != 2:
            raise AsiValidationError(
                "Un bonus unique doit être de **+2** à une caractéristique."
            )
    elif len(bonuses) == 2:
        if any(delta != 1 for delta in bonuses.values()):
            raise AsiValidationError(
                "Deux caractéristiques distinctes : **+1** chacune."
            )
        if len(set(bonuses.keys())) != 2:
            raise AsiValidationError(
                "Les deux bonus +1 doivent viser des caractéristiques différentes."
            )
    else:
        raise AsiValidationError(
            "Choisissez +2 à une carac ou +1/+1 à deux caracs."
        )

    effective = _effective_scores(base_scores, racial_bonuses)
    for ability_id, delta in bonuses.items():
        current = effective.get(ability_id, 10)
        if current + delta > MAX_ABILITY_SCORE:
            label = ABILITY_LABELS_FR.get(ability_id, ability_id)
            raise AsiValidationError(
                f"**{label}** ne peut pas dépasser **20** "
                f"(effectif {current}, bonus +{delta})."
            )

    return bonuses


def apply_asi_to_base(
    base: AbilityScores,
    bonuses: dict[str, int],
) -> AbilityScores:
    """Applique les bonus ASI sur les scores de base persistés."""
    scores = base.with_defaults(list(DEFAULT_ABILITY_IDS)).scores
    updated = dict(scores)
    for ability_id, delta in bonuses.items():
        updated[ability_id] = updated.get(ability_id, 10) + int(delta)
    return AbilityScores(scores=updated)


def asi_already_applied(choices: dict | None, level: int) -> bool:
    applied = (choices or {}).get("asi_applied") or []
    if not isinstance(applied, list):
        return False
    return any(
        isinstance(entry, dict) and int(entry.get("level", 0)) == level
        for entry in applied
    )


def record_asi_applied(
    choices: dict | None,
    level: int,
    bonuses: dict[str, int],
) -> dict:
    """Ajoute une entrée d'audit ; ne modifie pas les scores."""
    state = dict(choices or {})
    applied = list(state.get("asi_applied") or [])
    if not asi_already_applied(state, level):
        applied.append({"level": int(level), "bonuses": dict(bonuses)})
    state["asi_applied"] = applied
    return state


def eligible_asi_abilities(
    base_scores: dict[str, int],
    racial_bonuses: dict[str, int],
    *,
    increment: int = 1,
) -> tuple[str, ...]:
    """Caractéristiques pouvant recevoir ``increment`` sans dépasser le cap 20."""
    effective = _effective_scores(base_scores, racial_bonuses)
    eligible: list[str] = []
    for ability_id in DEFAULT_ABILITY_IDS:
        if effective.get(ability_id, 10) + increment <= MAX_ABILITY_SCORE:
            eligible.append(ability_id)
    return tuple(eligible)
