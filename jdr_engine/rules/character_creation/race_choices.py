# jdr_engine/rules/character_creation/race_choices.py
"""Choix raciaux à la création — ascendance draconique, Demi-elfe."""
from __future__ import annotations

from jdr_engine.rules.character_creation.class_choices import CreationChoiceError
from jdr_engine.rules.derived_stats import SKILL_LABELS_FR
from jdr_engine.rules.racial.draconic_ancestry import DRAGON_COLORS, get_draconic_ancestry
from jdr_engine.rules.racial.resolve import HALF_ELF_FLEXIBLE_ABILITIES

ALL_SKILL_IDS: tuple[str, ...] = tuple(SKILL_LABELS_FR.keys())

RACES_WITH_CREATION_STEP: frozenset[str] = frozenset({"dragonborn", "half_elf"})


def race_needs_creation_step(race_id: str) -> bool:
    return race_id in RACES_WITH_CREATION_STEP


def get_dragonborn_ancestry_options() -> tuple[str, ...]:
    return DRAGON_COLORS


def validate_dragonborn_ancestry(
    race_id: str,
    ancestry: str | None,
) -> str | None:
    if race_id != "dragonborn":
        return None
    if not ancestry or not str(ancestry).strip():
        raise CreationChoiceError(
            "Le Drakéide doit choisir une ascendance draconique."
        )
    color = str(ancestry).strip().lower()
    if get_draconic_ancestry(color) is None:
        raise CreationChoiceError(f"Ascendance draconique invalide : {color!r}.")
    return color


def validate_half_elf_ability_bonuses(
    race_id: str,
    bonuses: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    if race_id != "half_elf":
        return ()
    chosen = list(dict.fromkeys(str(a).strip().lower() for a in (bonuses or [])))
    if len(chosen) != 2:
        raise CreationChoiceError(
            "Demi-elfe : choisissez exactement 2 caractéristiques (+1 chacune, hors CHA)."
        )
    invalid = [a for a in chosen if a not in HALF_ELF_FLEXIBLE_ABILITIES]
    if invalid:
        raise CreationChoiceError(
            f"Caractéristiques invalides pour le Demi-elfe : {', '.join(invalid)}."
        )
    if len(set(chosen)) != 2:
        raise CreationChoiceError(
            "Demi-elfe : les deux caractéristiques doivent être différentes."
        )
    return tuple(chosen)


def validate_half_elf_skills(
    race_id: str,
    skills: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    if race_id != "half_elf":
        return ()
    chosen = list(dict.fromkeys(str(s) for s in (skills or [])))
    if len(chosen) != 2:
        raise CreationChoiceError(
            "Demi-elfe : choisissez exactement 2 compétences."
        )
    invalid = [s for s in chosen if s not in ALL_SKILL_IDS]
    if invalid:
        raise CreationChoiceError(
            f"Compétence(s) invalides : {', '.join(invalid)}."
        )
    return tuple(chosen)


def validate_race_creation_choices(
    race_id: str,
    *,
    draconic_ancestry: str | None = None,
    racial_ability_bonuses: list[str] | tuple[str, ...] | None = None,
    racial_skills: list[str] | tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Valide et normalise tous les choix raciaux pour ``finalize_new_character``."""
    result: dict[str, object] = {}
    ancestry = validate_dragonborn_ancestry(race_id, draconic_ancestry)
    if ancestry:
        result["draconic_ancestry"] = ancestry
    ability_picks = validate_half_elf_ability_bonuses(race_id, racial_ability_bonuses)
    if ability_picks:
        result["racial_ability_bonuses"] = list(ability_picks)
    skill_picks = validate_half_elf_skills(race_id, racial_skills)
    if skill_picks:
        result["racial_skills"] = list(skill_picks)
    return result
