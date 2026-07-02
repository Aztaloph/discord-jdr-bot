# jdr_engine/rules/class_features/monk.py
"""Moine — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

MARTIAL_ARTS_DIE_BY_LEVEL = (
    (1, 4, 4),
    (5, 10, 6),
    (11, 16, 8),
    (17, 20, 10),
)

KI_OPTIONS_LEVEL_2 = frozenset({
    "flurry_of_blows",
    "patient_defense",
    "step_of_the_wind",
})

KI_OPTION_COSTS = {
    "flurry_of_blows": 1,
    "patient_defense": 1,
    "step_of_the_wind": 1,
}


def martial_arts_die(level: int) -> int:
    """Dé d'arts martiaux (faces) selon niveau SRD 2014."""
    for low, high, faces in MARTIAL_ARTS_DIE_BY_LEVEL:
        if low <= level <= high:
            return faces
    return 4


def ki_max(wisdom_modifier: int) -> int:
    """Points de Ki = mod SAG (minimum 1 au niveau 2+)."""
    return max(1, wisdom_modifier)


def unarmored_movement_bonus(level: int) -> int:
    """Bonus vitesse sans armure (niv. 2+) : +10 ft / +3 m."""
    return 10 if level >= 2 else 0


def ki_options(level: int) -> frozenset[str]:
    """Options Ki disponibles (niv. 2+)."""
    if level < 2:
        return frozenset()
    return KI_OPTIONS_LEVEL_2


def deflect_missiles_can_throw(level: int, damage_reduced_to_zero: bool, ki_remaining: int) -> bool:
    """
    Dévier les projectiles (niv. 3) : lancer en retour si dégâts réduits à 0 et 1 Ki.
    """
    return level >= 3 and damage_reduced_to_zero and ki_remaining >= 1
