# jdr_engine/domain/character/character_sheet.py
"""Vue calculée d'un personnage — jamais persistée."""
from __future__ import annotations

from dataclasses import dataclass, field

from jdr_engine.domain.character.ability_scores import format_modifier


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
    initiative: int = 0
    saving_throws: tuple[str, ...] = ()
    proficient_skill_labels: tuple[str, ...] = ()
    hit_dice_remaining: int = 0
    hit_dice_total: int = 0
    specialization_id: str | None = None
    specialization_label: str | None = None
    fighting_style_id: str | None = None
    fighting_style_label: str | None = None
    trait_ids: list[str] = field(default_factory=list)
    trait_names: list[str] = field(default_factory=list)
    damage_resistances: str = ""
    innate_spells_text: str = ""
    xp: int = 0
    image_url: str | None = None

    def format_modifier(self, ability_id: str) -> str:
        mod = self.ability_modifiers.get(ability_id, 0)
        return format_modifier(mod)

    @property
    def class_display(self) -> str:
        """Classe + sous-classe si définie."""
        if self.specialization_label:
            return f"{self.class_name} ({self.specialization_label})"
        return self.class_name

    @property
    def hit_dice_display(self) -> str:
        return f"{self.hit_dice_remaining}/{self.hit_dice_total} {self.hit_die}"
