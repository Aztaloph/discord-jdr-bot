# jdr_engine/domain/combat/combat_state.py
"""État d'une rencontre — sérialisé en JSON (blob SQLite, lot C1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from jdr_engine.domain.combat.combatant import Combatant

COMBAT_STATE_VERSION = 1

CombatStatus = Literal["preparing", "active", "ended"]


class CombatStateVersionError(Exception):
    """Version de blob JSON non supportée."""


@dataclass
class CombatState:
    """
    Snapshot complet d'une rencontre.

    ``schema_version`` est la version du **modèle JSON** (distincte du schéma SQL).
    """

    schema_version: int
    ruleset_id: str
    round_number: int
    turn_index: int
    initiative_order: tuple[str, ...]
    combatants: dict[str, Combatant]
    status: CombatStatus
    started_at: str | None
    ended_at: str | None = None
    combat_id: str | None = None
    guild_id: str | None = None
    channel_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ruleset_id": self.ruleset_id,
            "round_number": self.round_number,
            "turn_index": self.turn_index,
            "initiative_order": list(self.initiative_order),
            "combatants": {
                cid: combatant.to_dict()
                for cid, combatant in self.combatants.items()
            },
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        combat_id: str | None = None,
        guild_id: str | None = None,
        channel_id: str | None = None,
    ) -> CombatState:
        version = int(data.get("schema_version", 0))
        if version != COMBAT_STATE_VERSION:
            raise CombatStateVersionError(
                f"Version de combat non supportée : {version} "
                f"(supportée : {COMBAT_STATE_VERSION})."
            )
        raw_combatants = data.get("combatants") or {}
        combatants = {
            str(key): Combatant.from_dict(value)
            for key, value in raw_combatants.items()
        }
        initiative = data.get("initiative_order") or []
        return cls(
            schema_version=version,
            ruleset_id=str(data.get("ruleset_id", "dnd5e")),
            round_number=int(data.get("round_number", 1)),
            turn_index=int(data.get("turn_index", 0)),
            initiative_order=tuple(str(x) for x in initiative),
            combatants=combatants,
            status=data.get("status", "active"),
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            combat_id=combat_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
