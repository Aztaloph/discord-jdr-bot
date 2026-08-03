# jdr_engine/domain/combat/combatant.py
"""Participant à une rencontre — lot C1 : PJ uniquement (ADR-004)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Combatant:
    """
    PJ rattaché à un ``character_id`` persisté.

    PV et CA sont un overlay de rencontre (lot C3a) — distincts de la fiche SQLite.
    """

    combatant_id: str
    display_name: str
    kind: Literal["player_character"]
    character_id: str
    hp_current: int
    hp_max: int
    ac: int
    is_active: bool = True
    initiative_total: int | None = None

    def to_dict(self) -> dict:
        payload = {
            "combatant_id": self.combatant_id,
            "display_name": self.display_name,
            "kind": self.kind,
            "character_id": self.character_id,
            "hp_current": self.hp_current,
            "hp_max": self.hp_max,
            "ac": self.ac,
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
            hp_current=int(data.get("hp_current", 0)),
            hp_max=int(data.get("hp_max", 0)),
            ac=int(data.get("ac", 10)),
            is_active=bool(data.get("is_active", True)),
            initiative_total=int(raw_init) if raw_init is not None else None,
        )

    def with_hp(self, hp_current: int) -> Combatant:
        """Retourne une copie avec les PV courants mis à jour."""
        return Combatant(
            combatant_id=self.combatant_id,
            display_name=self.display_name,
            kind=self.kind,
            character_id=self.character_id,
            hp_current=hp_current,
            hp_max=self.hp_max,
            ac=self.ac,
            is_active=self.is_active,
            initiative_total=self.initiative_total,
        )
