# jdr_engine/domain/combat/ — modèle de rencontre (lot C1+).
from jdr_engine.domain.combat.combat_state import (
    COMBAT_STATE_VERSION,
    CombatState,
    CombatStateVersionError,
)
from jdr_engine.domain.combat.combatant import Combatant

__all__ = [
    "COMBAT_STATE_VERSION",
    "CombatState",
    "CombatStateVersionError",
    "Combatant",
]
