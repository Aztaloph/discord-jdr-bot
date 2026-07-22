# jdr_engine/rules/character_progression/__init__.py
"""Progression de personnage — montée de niveau, ASI."""
from jdr_engine.rules.progression_constants import (
    MAX_CHARACTER_LEVEL,
    MAX_LEVEL_LOT2,
)
from jdr_engine.rules.character_progression.level_up import (
    LevelUpError,
    LevelUpPending,
    LevelUpPendingChoice,
    LevelUpResult,
    apply_level_up,
)

__all__ = [
    "LevelUpError",
    "LevelUpPending",
    "LevelUpPendingChoice",
    "LevelUpResult",
    "MAX_CHARACTER_LEVEL",
    "MAX_LEVEL_LOT2",
    "apply_level_up",
]
