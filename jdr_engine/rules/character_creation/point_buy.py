# jdr_engine/rules/character_creation/point_buy.py
"""Point buy SRD 2014 — 27 points, scores 8-15 avant bonus raciaux."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS

POINT_BUY_BUDGET = 27
POINT_BUY_MIN = 8
POINT_BUY_MAX = 15

# Coût cumulé depuis la base 8 (SRD / PHB 2014)
POINT_BUY_COSTS: dict[int, int] = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,
    15: 9,
}


class PointBuyError(ValueError):
    pass


def ability_score_cost(score: int) -> int:
    try:
        return POINT_BUY_COSTS[score]
    except KeyError as exc:
        raise PointBuyError(f"Score invalide pour le point buy : {score}") from exc


def points_spent(scores: dict[str, int]) -> int:
    return sum(ability_score_cost(scores[aid]) for aid in DEFAULT_ABILITY_IDS)


def points_remaining(scores: dict[str, int]) -> int:
    return POINT_BUY_BUDGET - points_spent(scores)


def validate_point_buy_scores(scores: dict[str, int]) -> None:
    for aid in DEFAULT_ABILITY_IDS:
        score = scores.get(aid, 8)
        if score < POINT_BUY_MIN or score > POINT_BUY_MAX:
            raise PointBuyError(
                f"{aid} = {score} : doit être entre {POINT_BUY_MIN} et {POINT_BUY_MAX}."
            )
    remaining = points_remaining(scores)
    if remaining < 0:
        raise PointBuyError(
            f"Dépassement du budget point buy ({POINT_BUY_BUDGET} pts)."
        )


def can_increase_score(scores: dict[str, int], ability_id: str) -> bool:
    current = scores.get(ability_id, POINT_BUY_MIN)
    if current >= POINT_BUY_MAX:
        return False
    next_score = current + 1
    trial = dict(scores)
    trial[ability_id] = next_score
    return points_remaining(trial) >= 0


def can_decrease_score(scores: dict[str, int], ability_id: str) -> bool:
    return scores.get(ability_id, POINT_BUY_MIN) > POINT_BUY_MIN
