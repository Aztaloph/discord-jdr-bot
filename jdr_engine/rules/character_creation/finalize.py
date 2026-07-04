# jdr_engine/rules/character_creation/finalize.py
"""Assemblage final d'un personnage niveau 1 — compatible moteur de sorts."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import AbilityScores, DEFAULT_ABILITY_IDS
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.class_choices import (
    CreationChoiceError,
    validate_cleric_domain,
    validate_skill_choices,
)
from jdr_engine.rules.character_creation.playable import PLAYABLE_CLASSES, PLAYABLE_RACES
from jdr_engine.rules.character_creation.point_buy import validate_point_buy_scores
from jdr_engine.rules.character_creation.race_choices import validate_race_creation_choices
from jdr_engine.rules.character_creation.starting_spells import build_starting_spellcasting
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.racial.resolve import build_tiefling_innate_spells
from jdr_engine.rules.spellcasting.spells_catalog import SUPPORTED_SPELLCASTING_CLASSES


def has_playable_subclass(class_id: str, engine: RuleEngine) -> bool:
    """True si une sous-classe doit être choisie à la création (niv. 1)."""
    from jdr_engine.rules.character_creation.class_choices import requires_domain_at_creation

    return requires_domain_at_creation(engine, class_id)


def finalize_new_character(
    *,
    name: str,
    race_id: str,
    class_id: str,
    owner_id: str,
    guild_id: str,
    base_scores: dict[str, int],
    engine: RuleEngine,
    level: int = 1,
    skills: list[str] | tuple[str, ...] | None = None,
    specialization: str | None = None,
    draconic_ancestry: str | None = None,
    racial_ability_bonuses: list[str] | tuple[str, ...] | None = None,
    racial_skills: list[str] | tuple[str, ...] | None = None,
) -> Character:
    """
    Construit un Character niveau 1 prêt pour SQLite et le moteur de sorts.

    ``base_scores`` : scores avant bonus raciaux (point buy 8–15).
    """
    if class_id not in PLAYABLE_CLASSES:
        raise ValueError(f"Classe non jouable : {class_id!r}")
    if race_id not in PLAYABLE_RACES:
        raise ValueError(f"Race non jouable : {race_id!r}")
    if level != 1:
        raise ValueError("Lot 1 : création limitée au niveau 1.")

    validate_point_buy_scores(base_scores)

    try:
        validated_skills = validate_skill_choices(engine, class_id, skills)
        domain = validate_cleric_domain(engine, class_id, specialization)
        racial_choices = validate_race_creation_choices(
            race_id,
            draconic_ancestry=draconic_ancestry,
            racial_ability_bonuses=racial_ability_bonuses,
            racial_skills=racial_skills,
        )
    except CreationChoiceError as exc:
        raise ValueError(str(exc)) from exc

    scores = {aid: int(base_scores.get(aid, 8)) for aid in DEFAULT_ABILITY_IDS}
    choices: dict = {}

    if validated_skills:
        choices["skills"] = list(validated_skills)

    if class_id in SUPPORTED_SPELLCASTING_CLASSES:
        choices["spellcasting"] = build_starting_spellcasting(class_id)

    if domain:
        choices["specialization"] = domain

    choices.update(racial_choices)

    if race_id == "tiefling":
        choices["innate_spells"] = build_tiefling_innate_spells()

    choices["rest"] = {
        "hit_dice_total": level,
        "hit_dice_remaining": level,
    }

    character = Character(
        owner_id=str(owner_id),
        guild_id=str(guild_id),
        name=name.strip(),
        race_id=race_id,
        class_id=class_id,
        level=level,
        ruleset_id=engine.ruleset_id,
        ruleset_version=engine.ruleset_version,
        ability_scores=AbilityScores(scores=scores),
        choices=choices,
    )

    sheet = build_character_sheet(character, engine)
    character.hp_max = sheet.hp_max
    character.hp_current = sheet.hp_max
    return character
