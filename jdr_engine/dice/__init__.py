# jdr_engine/dice — Parser et lanceur de dés (sans dépendance Discord).
from jdr_engine.dice.models import DiceError, MAX_DICE, MAX_FACES, RollResult
from jdr_engine.dice.parser import parse
from jdr_engine.dice.roller import roll

__all__ = [
    "DiceError",
    "MAX_DICE",
    "MAX_FACES",
    "RollResult",
    "parse",
    "roll",
]
