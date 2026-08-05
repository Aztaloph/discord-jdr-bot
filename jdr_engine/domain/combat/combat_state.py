# jdr_engine/domain/combat/combat_state.py
"""État d'une rencontre — sérialisé en JSON (blob SQLite, lot C1)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.domain.combat.active_effect import ActiveEffect

COMBAT_STATE_VERSION = 2

CombatStatus = Literal["preparing", "active", "ended"]

# Valeurs persistées en colonne SQL (index partiel lot C1 / C2).
SqlCombatStatus = Literal["preparing", "active", "ended"]


class CombatStateVersionError(Exception):
    """Version de blob JSON non supportée."""


def combat_status_from_sql(sql_status: str) -> CombatStatus:
    """Reconstruit le statut métier depuis la colonne SQL (source de vérité)."""
    if sql_status in ("preparing", "active", "ended"):
        return sql_status  # type: ignore[return-value]
    raise ValueError(f"Statut SQL combat inconnu : {sql_status!r}.")


def sql_status_from_combat(status: CombatStatus) -> SqlCombatStatus:
    """Projette le statut métier vers la colonne SQL."""
    return status


@dataclass
class CombatState:
    """
    Snapshot complet d'une rencontre.

    ``schema_version`` est la version du **modèle JSON** (distincte du schéma SQL).
    ``status`` vit en colonne SQL uniquement — absent du blob JSON (correctif C1a).
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
    active_effects: tuple[ActiveEffect, ...] = ()

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
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "active_effects": [
                effect.to_dict() for effect in self.active_effects
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        sql_status: str,
        combat_id: str | None = None,
        guild_id: str | None = None,
        channel_id: str | None = None,
    ) -> CombatState:
        """
        Désérialise le blob JSON.

        ``sql_status`` provient de la colonne SQL — seule source de vérité pour
        ``status``. Un champ ``status`` présent dans un blob legacy (C1) est ignoré.
        """
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
        raw_effects = data.get("active_effects") or []
        return cls(
            schema_version=version,
            ruleset_id=str(data.get("ruleset_id", "dnd5e")),
            round_number=int(data.get("round_number", 1)),
            turn_index=int(data.get("turn_index", 0)),
            initiative_order=tuple(str(x) for x in initiative),
            combatants=combatants,
            status=combat_status_from_sql(sql_status),
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            combat_id=combat_id,
            guild_id=guild_id,
            channel_id=channel_id,
            active_effects=tuple(
                ActiveEffect.from_dict(item) for item in raw_effects
            ),
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
