# tests/helpers/creation.py
"""Données valides pour créer des persos de test (Lots 1–5)."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS

WIZARD_SKILLS: tuple[str, ...] = ("arcana", "history")
CLERIC_SKILLS: tuple[str, ...] = ("medicine", "religion")
CLERIC_DOMAIN = "life"
SORCERER_SKILLS: tuple[str, ...] = ("arcana", "persuasion")
SORCERER_ORIGIN = "draconic"
SORCERER_DRAGON = "red"

FIGHTER_SKILLS: tuple[str, ...] = ("athletics", "perception")
BARBARIAN_SKILLS: tuple[str, ...] = ("athletics", "intimidation")
ROGUE_SKILLS: tuple[str, ...] = ("stealth", "perception", "acrobatics", "deception")
MONK_SKILLS: tuple[str, ...] = ("acrobatics", "athletics")
RANGER_SKILLS: tuple[str, ...] = ("survival", "perception", "stealth")
PALADIN_SKILLS: tuple[str, ...] = ("athletics", "persuasion")
BARD_SKILLS: tuple[str, ...] = ("performance", "persuasion", "deception")
LORE_BONUS_SKILLS: tuple[str, ...] = ("arcana", "history", "investigation")
DRUID_SKILLS: tuple[str, ...] = ("nature", "survival")
DRUID_CIRCLE = "land"
DRUID_TERRAIN = "forest"
WARLOCK_SKILLS: tuple[str, ...] = ("arcana", "deception")
WARLOCK_PATRON = "fiend"
WARLOCK_INVOCATIONS: tuple[str, ...] = ("agonizing_blast", "devils_sight")
WARLOCK_PACT_BOON = "pact_of_the_chain"


def valid_point_buy_scores(**overrides: int) -> dict[str, int]:
    """Scores 8–15 conformes point buy (défaut : tout à 8)."""
    scores = dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
    for key, value in overrides.items():
        scores[key] = value
    return scores


def wizard_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    base = dict(
        race_id="human",
        class_id="wizard",
        base_scores=valid_point_buy_scores(int=15, con=14),
        skills=list(WIZARD_SKILLS),
        level=level,
    )
    if level >= 2 and "specialization" not in overrides:
        base["specialization"] = "evocation"
    base.update(overrides)
    return base


def sorcerer_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    base = dict(
        race_id="human",
        class_id="sorcerer",
        base_scores=valid_point_buy_scores(cha=15, dex=14, con=14),
        skills=list(SORCERER_SKILLS),
        specialization=SORCERER_ORIGIN,
        sorcerer_dragon_type=SORCERER_DRAGON,
        level=level,
    )
    if level >= 3 and "metamagic_options" not in overrides:
        base["metamagic_options"] = ["quickened", "subtle"]
    base.update(overrides)
    return base


def cleric_creation_kwargs(**overrides) -> dict:
    base = dict(
        race_id="human",
        class_id="cleric",
        base_scores=valid_point_buy_scores(wis=15, con=14),
        skills=list(CLERIC_SKILLS),
        specialization=CLERIC_DOMAIN,
    )
    base.update(overrides)
    return base


def druid_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    base = dict(
        race_id="human",
        class_id="druid",
        base_scores=valid_point_buy_scores(wis=15, con=14),
        skills=list(DRUID_SKILLS),
        level=level,
    )
    if level >= 2:
        base["specialization"] = DRUID_CIRCLE
        base["druid_land_terrain"] = DRUID_TERRAIN
    base.update(overrides)
    return base


def warlock_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    base = dict(
        race_id="human",
        class_id="warlock",
        base_scores=valid_point_buy_scores(cha=15, con=14),
        skills=list(WARLOCK_SKILLS),
        specialization=WARLOCK_PATRON,
        level=level,
    )
    if level >= 2 and "eldritch_invocations" not in overrides:
        base["eldritch_invocations"] = list(WARLOCK_INVOCATIONS)
    if level >= 3 and "pact_boon" not in overrides:
        base["pact_boon"] = WARLOCK_PACT_BOON
    base.update(overrides)
    return base


def fighter_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    base = dict(
        race_id="human",
        class_id="fighter",
        base_scores=valid_point_buy_scores(con=14),
        skills=list(FIGHTER_SKILLS),
        fighting_style="defense",
        level=level,
    )
    base.update(overrides)
    return base


def barbarian_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    base = dict(
        race_id="human",
        class_id="barbarian",
        base_scores=valid_point_buy_scores(con=14, dex=10),
        skills=list(BARBARIAN_SKILLS),
        level=level,
    )
    base.update(overrides)
    return base


def rogue_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    skills = list(overrides.pop("skills", list(ROGUE_SKILLS)))
    expertise = list(overrides.pop("expertise_skills", skills[:2]))
    base = dict(
        race_id="human",
        class_id="rogue",
        base_scores=valid_point_buy_scores(dex=15, con=14),
        skills=skills,
        expertise_skills=expertise,
        level=level,
    )
    base.update(overrides)
    return base


def monk_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    base = dict(
        race_id="human",
        class_id="monk",
        base_scores=valid_point_buy_scores(dex=15, wis=14, con=14),
        skills=list(MONK_SKILLS),
        level=level,
    )
    base.update(overrides)
    return base


def ranger_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    base = dict(
        race_id="human",
        class_id="ranger",
        base_scores=valid_point_buy_scores(wis=15, dex=14, con=14),
        skills=list(RANGER_SKILLS),
        favored_enemy_type="beasts",
        favored_terrain="forest",
        level=level,
    )
    if level >= 2 and "fighting_style" not in overrides:
        base["fighting_style"] = "archery"
    base.update(overrides)
    return base


def paladin_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    base = dict(
        race_id="human",
        class_id="paladin",
        base_scores=valid_point_buy_scores(str=15, cha=14, con=14),
        skills=list(PALADIN_SKILLS),
        level=level,
    )
    if level >= 2 and "fighting_style" not in overrides:
        base["fighting_style"] = "defense"
    base.update(overrides)
    return base


def bard_creation_kwargs(**overrides) -> dict:
    level = overrides.pop("level", 1)
    skills = list(overrides.pop("skills", list(BARD_SKILLS)))
    expertise = list(overrides.pop("expertise_skills", skills[:2]))
    lore_bonus = list(overrides.pop("lore_bonus_skills", list(LORE_BONUS_SKILLS)))
    base = dict(
        race_id="human",
        class_id="bard",
        base_scores=valid_point_buy_scores(cha=15, dex=14, con=14),
        skills=skills,
        level=level,
    )
    if level >= 3:
        base["specialization"] = "lore"
        base["expertise_skills"] = expertise
        base["lore_bonus_skills"] = lore_bonus
    base.update(overrides)
    return base
