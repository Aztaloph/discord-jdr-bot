# interfaces/discord/handlers/d20_notation.py
"""Normalisation notation d20 pour /roll Discord (SRD 2014 avantage = max, pas somme)."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.dice import DiceError, parse

from interfaces.discord.handlers.combat_roll import CombatRollFlags


@dataclass(frozen=True)
class NormalizedD20Roll:
    """Entrée normalisée pour le hook ``roll_d20_for_character``."""

    ability_modifier: int
    sign: str
    mode: str
    from_double_notation: bool = False


def normalize_d20_roll_input(
    dice_str: str,
    mode: str,
    combat: CombatRollFlags,
) -> NormalizedD20Roll | None:
    """
    Détecte un jet d20 éligible au hook personnage.

    - ``d20`` / ``1d20+4`` → 1d20
    - ``2d20+4`` → avantage SRD (meilleur gardé), **pas** somme des deux dés
    - ``impetueux:True`` + ``d20`` → mode avantage automatique
    """
    count, faces, modifier, sign = parse(dice_str)
    if faces != 20:
        return None

    if count > 2:
        raise DiceError(
            f'Notation « {dice_str} » : pour un jet d20 avec avantage SRD 2014, '
            "utilisez `d20+mod` (ou `impetueux:True`) — pas 3d20 ou plus."
        )

    effective_mode = mode
    from_double = False

    if count == 2:
        from_double = True
        if mode == "desavantage":
            raise DiceError(
                "« 2d20 » avec mode Désavantage est ambigu. "
                "Utilisez `d20+mod` avec le mode Désavantage."
            )
        effective_mode = "avantage"

    # Impétueux : avantage automatique (le joueur tape d20, pas 2d20)
    if combat.reckless and effective_mode == "normal":
        effective_mode = "avantage"

    if mode == "avantage" and effective_mode == "normal":
        effective_mode = "avantage"

    return NormalizedD20Roll(
        ability_modifier=modifier,
        sign=sign,
        mode=effective_mode,
        from_double_notation=from_double,
    )


def is_hook_eligible_d20(dice_str: str) -> bool:
    """True si la notation peut passer par le hook d20 (1 ou 2 × d20)."""
    try:
        count, faces, _, _ = parse(dice_str)
    except DiceError:
        return False
    return faces == 20 and 1 <= count <= 2
