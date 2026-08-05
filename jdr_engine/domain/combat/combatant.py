# jdr_engine/domain/combat/combatant.py
"""Participant à une rencontre — lot C1 : PJ uniquement (ADR-004)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from jdr_engine.domain.combat.action_budget import ActionBudget, ActionKind, fresh_action_budget


@dataclass(frozen=True)
class Combatant:
    """
    PJ rattaché à un ``character_id`` persisté.

    PV et CA sont un overlay de rencontre (lot C3a) — distincts de la fiche SQLite.
    Concentration et buffs de sort (C3b) vivent aussi dans l'overlay combat.
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
    concentration_spell_id: str | None = None
    concentration_spell_name: str | None = None
    hunters_mark_caster_id: str | None = None
    blessed: bool = False
    action_budget: ActionBudget | None = None
    conditions: tuple[str, ...] = ()

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
        if self.concentration_spell_id is not None:
            payload["concentration_spell_id"] = self.concentration_spell_id
            payload["concentration_spell_name"] = self.concentration_spell_name
        if self.hunters_mark_caster_id is not None:
            payload["hunters_mark_caster_id"] = self.hunters_mark_caster_id
        if self.blessed:
            payload["blessed"] = True
        if self.action_budget is not None:
            payload["action_budget"] = self.action_budget.to_dict()
        if self.conditions:
            payload["conditions"] = list(self.conditions)
        return payload

    @classmethod
    def from_dict(cls, data: dict) -> Combatant:
        raw_init = data.get("initiative_total")
        conc_id = data.get("concentration_spell_id")
        conc_name = data.get("concentration_spell_name")
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
            concentration_spell_id=str(conc_id) if conc_id is not None else None,
            concentration_spell_name=str(conc_name) if conc_name is not None else None,
            hunters_mark_caster_id=(
                str(data["hunters_mark_caster_id"])
                if data.get("hunters_mark_caster_id")
                else None
            ),
            blessed=bool(data.get("blessed", False)),
            action_budget=(
                ActionBudget.from_dict(raw_budget)
                if (raw_budget := data.get("action_budget")) is not None
                else None
            ),
            conditions=tuple(
                str(condition_id)
                for condition_id in (data.get("conditions") or [])
            ),
        )

    def with_hp(self, hp_current: int) -> Combatant:
        """Met à jour les PV ; à 0 PV le combattant quitte la rotation (ADR-005 §1)."""
        updates: dict = {"hp_current": hp_current}
        if hp_current <= 0:
            updates["is_active"] = False
        return replace(self, **updates)

    def with_concentration(
        self,
        spell_id: str,
        spell_name: str,
    ) -> Combatant:
        return replace(
            self,
            concentration_spell_id=spell_id,
            concentration_spell_name=spell_name,
        )

    def without_concentration(self) -> Combatant:
        return replace(
            self,
            concentration_spell_id=None,
            concentration_spell_name=None,
        )

    def with_hunters_mark(self, caster_id: str) -> Combatant:
        return replace(self, hunters_mark_caster_id=caster_id)

    def with_blessed(self, blessed: bool = True) -> Combatant:
        return replace(self, blessed=blessed)

    def without_hunters_mark(self) -> Combatant:
        return replace(self, hunters_mark_caster_id=None)

    def without_blessed(self) -> Combatant:
        return replace(self, blessed=False)

    def with_action_budget(self, budget: ActionBudget | None) -> Combatant:
        return replace(self, action_budget=budget)

    def with_condition(self, condition_id: str) -> Combatant:
        if condition_id in self.conditions:
            return self
        return replace(self, conditions=self.conditions + (condition_id,))

    def without_condition(self, condition_id: str) -> Combatant:
        if condition_id not in self.conditions:
            return self
        return replace(
            self,
            conditions=tuple(c for c in self.conditions if c != condition_id),
        )
