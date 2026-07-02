# jdr_engine/dice/models.py
# Structures de données et exceptions pour le système de dés.
from dataclasses import dataclass


class DiceError(Exception):
    """Exception personnalisée pour les erreurs de lancer de dés."""

    pass


MAX_DICE = 100
MAX_FACES = 1000


@dataclass
class RollResult:
    """
    Résultat d'un lancer de dés.

    Attributs :
        dice_notation  — notation du lancer (ex : "3d6+2")
        rolls          — liste des résultats de chaque dé individuel
        modifier       — modificateur appliqué (ex : +2 ou -1)
        modifier_label — label textuel du modificateur (ex : "+2" ou "-1")
        total          — total final (somme des dés conservés + modificateur)
        is_kept        — True si le dé est gardé (avantage/désavantage)
    """

    dice_notation: str
    rolls: list[int]
    modifier: int
    modifier_label: str
    total: int
    is_kept: list[bool]
