# jdr_engine/domain/character/ability_scores.py
"""Scores de caractéristiques — ids Compendium (str, dex, con…)."""
from __future__ import annotations

from dataclasses import dataclass, field

# Mapping legacy v1 (français) → ids Compendium v2
LEGACY_ABILITY_MAP: dict[str, str] = {
    "force": "str",
    "dexterite": "dex",
    "constitution": "con",
    "intelligence": "int",
    "sagesse": "wis",
    "charisme": "cha",
}

DEFAULT_ABILITY_IDS: tuple[str, ...] = ("str", "dex", "con", "int", "wis", "cha")


def ability_modifier(score: int) -> int:
    """Modificateur D&D 5e : (score - 10) // 2."""
    return (score - 10) // 2


def format_modifier(mod: int) -> str:
    return f"+{mod}" if mod >= 0 else str(mod)


@dataclass
class AbilityScores:
    """Value object — scores bruts du joueur (avant bonus raciaux)."""

    scores: dict[str, int] = field(default_factory=lambda: dict.fromkeys(DEFAULT_ABILITY_IDS, 10))

    def get(self, ability_id: str, default: int = 10) -> int:
        return self.scores.get(ability_id, default)

    def to_dict(self) -> dict[str, int]:
        return dict(self.scores)

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> AbilityScores:
        return cls(scores=dict(data))

    @classmethod
    def from_legacy(cls, legacy: dict[str, int]) -> AbilityScores:
        """Convertit les clés françaises v1 vers ids Compendium."""
        converted: dict[str, int] = dict.fromkeys(DEFAULT_ABILITY_IDS, 10)
        for key, value in legacy.items():
            ability_id = LEGACY_ABILITY_MAP.get(key.lower(), key.lower())
            if ability_id in DEFAULT_ABILITY_IDS:
                converted[ability_id] = int(value)
        return cls(scores=converted)

    def with_defaults(self, ability_ids: list[str]) -> AbilityScores:
        merged = dict.fromkeys(ability_ids, 10)
        merged.update(self.scores)
        return AbilityScores(scores=merged)
