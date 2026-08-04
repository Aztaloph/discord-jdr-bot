# jdr_engine/domain/combat/action_budget.py
"""Budget d'actions par tour — lot C4 (SRD 5.1 2014)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

ActionKind = Literal["action", "bonus_action", "reaction", "movement"]

_FIELD_BY_KIND: dict[ActionKind, str] = {
    "action": "has_action",
    "bonus_action": "has_bonus_action",
    "reaction": "has_reaction",
    "movement": "has_movement",
}


class ActionBudgetExhaustedError(Exception):
    """Composante du budget déjà consommée pour le tour courant."""


@dataclass(frozen=True)
class ActionBudget:
    """Une action, une action bonus, une réaction, un déplacement par tour."""

    has_action: bool = True
    has_bonus_action: bool = True
    has_reaction: bool = True
    has_movement: bool = True

    def consume(self, kind: ActionKind) -> ActionBudget:
        """Retourne un budget avec ``kind`` consommé ; lève si déjà épuisé."""
        field = _FIELD_BY_KIND[kind]
        if not getattr(self, field):
            raise ActionBudgetExhaustedError(
                f"Budget épuisé pour {kind!r}."
            )
        return replace(self, **{field: False})

    def to_dict(self) -> dict[str, bool]:
        return {
            "has_action": self.has_action,
            "has_bonus_action": self.has_bonus_action,
            "has_reaction": self.has_reaction,
            "has_movement": self.has_movement,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionBudget:
        return cls(
            has_action=bool(data.get("has_action", True)),
            has_bonus_action=bool(data.get("has_bonus_action", True)),
            has_reaction=bool(data.get("has_reaction", True)),
            has_movement=bool(data.get("has_movement", True)),
        )


def fresh_action_budget() -> ActionBudget:
    """Budget complet — réinitialisé au ``TurnStarted`` du combattant."""
    return ActionBudget()
