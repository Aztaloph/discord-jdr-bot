"""
Re-export legacy — préférer : from jdr_engine.dice import ...

Conservé pour compatibilité avec bot/cogs/dice.py pendant la migration.
Sera supprimé en Phase 10.
"""
from jdr_engine.dice import (
    DiceError,
    MAX_DICE,
    MAX_FACES,
    RollResult,
    parse,
    roll,
)

__all__ = [
    "DiceError",
    "MAX_DICE",
    "MAX_FACES",
    "RollResult",
    "parse",
    "roll",
]
