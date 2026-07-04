# jdr_engine/rules/character_creation/random_assign.py
"""Assignation des jets 4d6 aux caractéristiques (SRD 2014)."""
from __future__ import annotations

from dataclasses import dataclass, field

from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS
from typing import Callable

from jdr_engine.rules.character_creation.rolling import roll_ability_score_pool

RandInt = Callable[[int, int], int]


@dataclass
class RolledEntry:
    index: int
    value: int
    ability_id: str | None = None


@dataclass
class RandomAssignState:
    """État d'assignation — indices uniques pour Discord Select."""

    entries: list[RolledEntry] = field(default_factory=list)
    pending_ability: str | None = None
    pending_roll_index: int | None = None

    @classmethod
    def from_pool(cls, pool: list[int]) -> RandomAssignState:
        return cls(
            entries=[
                RolledEntry(index=i, value=value) for i, value in enumerate(pool)
            ]
        )

    @classmethod
    def roll_new(cls, *, rng: RandInt | None = None) -> RandomAssignState:
        return cls.from_pool(roll_ability_score_pool(rng=rng))

    def unassigned_abilities(self) -> list[str]:
        assigned = {e.ability_id for e in self.entries if e.ability_id}
        return [aid for aid in DEFAULT_ABILITY_IDS if aid not in assigned]

    def unassigned_roll_indices(self) -> list[int]:
        return [e.index for e in self.entries if e.ability_id is None]

    def assign(self, ability_id: str, roll_index: int) -> None:
        if ability_id not in DEFAULT_ABILITY_IDS:
            raise ValueError(f"Caractéristique invalide : {ability_id!r}")
        entry = self._entry_by_index(roll_index)
        if entry is None:
            raise ValueError(f"Jet invalide : {roll_index}")
        if entry.ability_id is not None:
            raise ValueError(f"Jet {roll_index} déjà assigné.")
        if any(e.ability_id == ability_id for e in self.entries):
            raise ValueError(f"{ability_id} a déjà un jet assigné.")
        entry.ability_id = ability_id
        self.pending_ability = None
        self.pending_roll_index = None

    def is_complete(self) -> bool:
        return all(e.ability_id is not None for e in self.entries)

    def to_base_scores(self) -> dict[str, int]:
        if not self.is_complete():
            raise ValueError("Assignation incomplète.")
        scores: dict[str, int] = {}
        for entry in self.entries:
            assert entry.ability_id is not None
            scores[entry.ability_id] = entry.value
        return scores

    def _entry_by_index(self, roll_index: int) -> RolledEntry | None:
        for entry in self.entries:
            if entry.index == roll_index:
                return entry
        return None

    def pool_values(self) -> list[int]:
        return [e.value for e in self.entries]

    def sorted_pool_values(self) -> list[int]:
        """Affichage uniquement — jets triés du plus grand au plus petit."""
        return sorted(self.pool_values(), reverse=True)

    def score_for_ability(self, ability_id: str) -> int | None:
        for entry in self.entries:
            if entry.ability_id == ability_id:
                return entry.value
        return None

    def clear_assignment(self, ability_id: str) -> None:
        for entry in self.entries:
            if entry.ability_id == ability_id:
                entry.ability_id = None
                return
