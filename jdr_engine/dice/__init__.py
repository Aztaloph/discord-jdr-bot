# jdr_engine/dice — Parser et lanceur de dés (sans dépendance Discord).
from jdr_engine.dice.d20 import (
    D20RollContext,
    D20RollRequest,
    D20RollResult,
    roll_d20,
)
from jdr_engine.dice.models import DiceError, MAX_DICE, MAX_FACES, RollResult
from jdr_engine.dice.parser import parse
from jdr_engine.dice.roller import roll

__all__ = [
    "DiceError",
    "D20RollContext",
    "D20RollRequest",
    "D20RollResult",
    "MAX_DICE",
    "MAX_FACES",
    "RollResult",
    "parse",
    "roll",
    "roll_d20",
]
