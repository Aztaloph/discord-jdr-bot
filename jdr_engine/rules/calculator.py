# jdr_engine/rules/calculator.py
"""Calcul des statistiques dérivées depuis Compendium + Character."""
from __future__ import annotations

import re

from jdr_engine.domain.character.ability_scores import (
    DEFAULT_ABILITY_IDS,
    ability_modifier,
)
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.character_sheet import CharacterSheet
from jdr_engine.rules.engine import RuleEngine


class CharacterBuildError(Exception):
    """Impossible de construire la fiche (données invalides)."""


def parse_hit_die(hit_die: str) -> int:
    """Convertit 'd10' → 10."""
    match = re.fullmatch(r"d(\d+)", hit_die.strip().lower())
    if not match:
        raise CharacterBuildError(f"Dé de vie invalide : {hit_die!r}")
    return int(match.group(1))


def apply_racial_bonuses(
    base_scores: dict[str, int],
    racial_bonuses: dict[str, int],
) -> dict[str, int]:
    effective = dict(base_scores)
    for ability_id, bonus in racial_bonuses.items():
        effective[ability_id] = effective.get(ability_id, 10) + bonus
    return effective


def calculate_hp_max_level_1(hit_die_faces: int, con_modifier: int) -> int:
    """PV niveau 1 : maximum du dé de vie + mod CON."""
    return max(1, hit_die_faces + con_modifier)


def calculate_ac_unarmored(dex_modifier: int) -> int:
    """CA sans armure (simplifié Phase 2) : 10 + mod DEX."""
    return 10 + dex_modifier


def build_character_sheet(
    character: Character,
    engine: RuleEngine,
    *,
    locale: str = "fr",
) -> CharacterSheet:
    """
    Construit une fiche calculée à partir de l'état Character + Rule Engine.
    """
    if character.ruleset_id != engine.ruleset_id:
        raise CharacterBuildError(
            f"Ruleset personnage ({character.ruleset_id}) "
            f"≠ moteur ({engine.ruleset_id})"
        )

    race = engine.get_entity("race", character.race_id)
    class_entry = engine.get_entity("class", character.class_id)
    if race is None:
        raise CharacterBuildError(f"Race inconnue : {character.race_id!r}")
    if class_entry is None:
        raise CharacterBuildError(f"Classe inconnue : {character.class_id!r}")

    ability_ids = [a.id for a in engine.registry.config.abilities] or list(
        DEFAULT_ABILITY_IDS
    )
    base_scores = character.ability_scores.with_defaults(ability_ids).scores

    racial_bonuses = engine.get_ability_bonuses(character.race_id)
    effective_scores = apply_racial_bonuses(base_scores, racial_bonuses)
    modifiers = {aid: ability_modifier(score) for aid, score in effective_scores.items()}

    hit_die = engine.get_class_hit_die(character.class_id)
    if not hit_die:
        raise CharacterBuildError(f"hit_die manquant pour {character.class_id!r}")

    hit_die_faces = parse_hit_die(hit_die)
    con_mod = modifiers.get("con", 0)
    proficiency = engine.get_proficiency_bonus(character.level)

    if character.level == 1:
        hp_max = calculate_hp_max_level_1(hit_die_faces, con_mod)
    else:
        # MVP Phase 2 : approximation niveaux > 1
        hp_max = calculate_hp_max_level_1(hit_die_faces, con_mod)
        hp_max += (character.level - 1) * (hit_die_faces // 2 + 1 + con_mod)
        hp_max = max(1, hp_max)

    hp_current = character.hp_current if character.hp_current is not None else hp_max
    hp_current = min(hp_current, hp_max)

    dex_mod = modifiers.get("dex", 0)
    ac = calculate_ac_unarmored(dex_mod)
    speed = int(race.definition.mechanics.get("speed", 30))

    traits = engine.get_race_traits(character.race_id)
    trait_ids = [t.entry_id for t in traits]
    trait_names = [
        t.get_name(locale, engine.registry.manifest.default_locale) for t in traits
    ]

    race_name = race.get_name(locale, engine.registry.manifest.default_locale)
    class_name = class_entry.get_name(
        locale, engine.registry.manifest.default_locale
    )

    return CharacterSheet(
        character_id=character.id,
        name=character.name,
        owner_id=character.owner_id,
        ruleset_id=character.ruleset_id,
        race_id=character.race_id,
        race_name=race_name,
        class_id=character.class_id,
        class_name=class_name,
        level=character.level,
        ability_scores_base=dict(base_scores),
        ability_scores=effective_scores,
        ability_modifiers=modifiers,
        proficiency_bonus=proficiency,
        hit_die=hit_die,
        hp_max=hp_max,
        hp_current=hp_current,
        ac=ac,
        speed=speed,
        trait_ids=trait_ids,
        trait_names=trait_names,
        xp=character.xp,
        image_url=character.image_url,
    )
