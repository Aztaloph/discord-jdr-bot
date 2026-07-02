# jdr_engine/domain/character/character_sheet.py
"""Vue calculée d'un personnage — jamais persistée."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CharacterSheet:
    """Fiche personnage dérivée du Compendium + état Character."""

    character_id: str
    name: str
    owner_id: str
    ruleset_id: str
    race_id: str
    race_name: str
    class_id: str
    class_name: str
    level: int
    ability_scores_base: dict[str, int]
    ability_scores: dict[str, int]
    ability_modifiers: dict[str, int]
    proficiency_bonus: int
    hit_die: str
    hp_max: int
    hp_current: int
    ac: int
    speed: int
    trait_ids: list[str] = field(default_factory=list)
    trait_names: list[str] = field(default_factory=list)
    xp: int = 0
    image_url: str | None = None

    def format_modifier(self, ability_id: str) -> str:
        mod = self.ability_modifiers.get(ability_id, 0)
        return f"+{mod}" if mod >= 0 else str(mod)
