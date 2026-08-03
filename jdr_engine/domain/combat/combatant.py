# jdr_engine/domain/combat/combatant.py
"""Participant à une rencontre — lot C1 : PJ uniquement (ADR-004)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Combatant:
    """PJ rattaché à un ``character_id`` persisté — pas de stats injectées."""

    combatant_id: str
    display_name: str
    kind: Literal["player_character"]
    character_id: str
    is_active: bool = True
    initiative_total: int | None = None

    def to_dict(self) -> dict:
        payload = {
            "combatant_id": self.combatant_id,
            "display_name": self.display_name,
            "kind": self.kind,
            "character_id": self.character_id,
            "is_active": self.is_active,
        }
        if self.initiative_total is not None:
            payload["initiative_total"] = self.initiative_total
        return payload

    @classmethod
    def from_dict(cls, data: dict) -> Combatant:
        raw_init = data.get("initiative_total")
        return cls(
            combatant_id=str(data["combatant_id"]),
            display_name=str(data["display_name"]),
            kind="player_character",
            character_id=str(data["character_id"]),
            is_active=bool(data.get("is_active", True)),
            initiative_total=int(raw_init) if raw_init is not None else None,
        )
