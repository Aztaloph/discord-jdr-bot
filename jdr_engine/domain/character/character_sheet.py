# jdr_engine/domain/character/character_sheet.py
"""Vue calculée d'un personnage — jamais persistée."""
from __future__ import annotations

from dataclasses import dataclass, field

from jdr_engine.domain.character.ability_scores import format_modifier


@dataclass(frozen=True)
class SavingThrowEntry:
    """Jet de sauvegarde structuré — équivalent données de ``saving_throws`` (texte)."""

    ability_id: str
    modifier: int
    proficient: bool


@dataclass(frozen=True)
class ClassFeatureRef:
    """Aptitude de classe (id + libellé) — sans compteurs de ressources."""

    feature_id: str
    name: str


@dataclass(frozen=True)
class InnateSpellEntry:
    """Sort inné racial — équivalent structuré d'``innate_spells_text``."""

    spell_id: str
    usage: str  # "at_will" | "one_per_long_rest"
    min_level: int


@dataclass(frozen=True)
class SpellcastingView:
    """Bloc incantation structuré — équivalent données de ``spellcasting_summary``."""

    ability: str | None = None
    pact_magic: bool = False
    slots_max: dict[int, int] = field(default_factory=dict)
    slots_remaining: dict[int, int] = field(default_factory=dict)
    concentration_spell_id: str | None = None
    concentration_spell_name: str | None = None
    cantrips_known: tuple[str, ...] = ()
    spells_prepared: tuple[str, ...] = ()
    spells_known: tuple[str, ...] = ()
    spellbook: tuple[str, ...] = ()
    domain_spells: tuple[str, ...] = ()


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
    armor_proficiencies_text: str = ""
    weapon_proficiencies_text: str = ""
    spellcasting_summary: str | None = None
    trait_ids: list[str] = field(default_factory=list)
    trait_names: list[str] = field(default_factory=list)
    damage_resistances: str = ""
    innate_spells_text: str = ""
    class_features_lines: tuple[str, ...] = ()
    xp: int = 0
    image_url: str | None = None
    # Équivalents structurés des champs d'affichage ci-dessus (lot DTO/API).
    # Les champs *_text / *_labels / *_lines restent en place pour Discord ;
    # les DTO n'exposent que les champs structurés.
    saving_throw_entries: tuple[SavingThrowEntry, ...] = ()
    proficient_skill_ids: tuple[str, ...] = ()
    armor_proficiencies: tuple[str, ...] = ()
    weapon_proficiencies: tuple[str, ...] = ()
    damage_resistance_ids: tuple[str, ...] = ()
    innate_spells: tuple[InnateSpellEntry, ...] = ()
    class_features: tuple[ClassFeatureRef, ...] = ()
    spellcasting: SpellcastingView | None = None

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
