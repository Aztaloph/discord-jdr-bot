# tests/helpers/creation.py
"""Données valides pour créer des persos de test (Lot 1 — point buy + choix)."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS

WIZARD_SKILLS: tuple[str, ...] = ("arcana", "history")
CLERIC_SKILLS: tuple[str, ...] = ("medicine", "religion")
CLERIC_DOMAIN = "life"


def valid_point_buy_scores(**overrides: int) -> dict[str, int]:
    """Scores 8–15 conformes point buy (défaut : tout à 8)."""
    scores = dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
    for key, value in overrides.items():
        scores[key] = value
    return scores


def wizard_creation_kwargs(**overrides) -> dict:
    base = dict(
        race_id="human",
        class_id="wizard",
        base_scores=valid_point_buy_scores(int=15, con=14),
        skills=list(WIZARD_SKILLS),
    )
    base.update(overrides)
    return base


def cleric_creation_kwargs(**overrides) -> dict:
    base = dict(
        race_id="human",
        class_id="cleric",
        base_scores=valid_point_buy_scores(wis=15, con=14),
        skills=list(CLERIC_SKILLS),
        specialization=CLERIC_DOMAIN,
    )
    base.update(overrides)
    return base
