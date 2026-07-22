# jdr_engine/rules/calculator.py
"""Calcul des statistiques dérivées depuis Compendium + Character."""
from __future__ import annotations

import re

from jdr_engine.domain.character.ability_scores import (
    DEFAULT_ABILITY_IDS,
    ability_modifier,
)
from jdr_engine.domain.character.effective_scores import compute_effective_ability_scores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.character_sheet import CharacterSheet
from jdr_engine.rules.derived_stats import (
    apply_class_hp_bonus,
    build_saving_throws,
    calculate_armor_class,
    calculate_hp_max,
    calculate_initiative,
    collect_proficient_skills,
    read_hit_dice,
    resolve_fighting_style_label,
    resolve_specialization_label,
    skill_label_fr,
)
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.racial.resolve import (
    format_innate_spells_display,
    format_resistances_display,
    get_damage_resistances,
    get_racial_ability_bonuses,
    resolve_race_trait_labels,
)

# Réexport compatibilité tests / imports existants
__all__ = [
    "CharacterBuildError",
    "ability_modifier",
    "apply_racial_bonuses",
    "build_character_sheet",
    "calculate_ac_unarmored",
    "calculate_hp_max_level_1",
    "parse_hit_die",
]


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
    return compute_effective_ability_scores(base_scores, racial_bonuses)


def calculate_hp_max_level_1(hit_die_faces: int, con_modifier: int) -> int:
    """PV niveau 1 : maximum du dé de vie + mod CON."""
    return max(1, hit_die_faces + con_modifier)


def calculate_ac_unarmored(dex_modifier: int) -> int:
    """CA sans armure (fallback) : 10 + mod DEX."""
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

    racial_bonuses = get_racial_ability_bonuses(character, engine)
    effective_scores = apply_racial_bonuses(base_scores, racial_bonuses)
    modifiers = {aid: ability_modifier(score) for aid, score in effective_scores.items()}

    hit_die = engine.get_class_hit_die(character.class_id)
    if not hit_die:
        raise CharacterBuildError(f"hit_die manquant pour {character.class_id!r}")

    hit_die_faces = parse_hit_die(hit_die)
    con_mod = modifiers.get("con", 0)
    proficiency = engine.get_proficiency_bonus(character.level)

    if character.hp_max is not None:
        hp_max = max(1, int(character.hp_max))
    else:
        hp_max = calculate_hp_max(
            character.level,
            hit_die_faces,
            con_mod,
        )
        hp_max = apply_class_hp_bonus(character, hp_max)

    hp_current = character.hp_current if character.hp_current is not None else hp_max
    hp_current = min(hp_current, hp_max)

    dex_mod = modifiers.get("dex", 0)
    ac = calculate_armor_class(character, engine, modifiers)
    initiative = calculate_initiative(dex_mod)
    speed = int(race.definition.mechanics.get("speed", 30))
    if character.class_id == "monk":
        from jdr_engine.rules.class_features.monk import unarmored_movement_bonus

        speed += unarmored_movement_bonus(character.level)

    from jdr_engine.rules.character_creation.class_basics import (
        format_armor_proficiencies,
        format_spellcasting_summary,
        format_weapon_proficiencies,
    )

    from jdr_engine.domain.character.choices_schema import get_specialization_id
    from jdr_engine.rules.class_features.cleric import collect_bonus_armor_proficiencies
    from jdr_engine.rules.spellcasting.state import format_spellcasting_detail

    armor_bonus = collect_bonus_armor_proficiencies(
        get_specialization_id(character.choices)
    )
    spell_summary = format_spellcasting_summary(
        engine, character.class_id, character_level=character.level
    )
    if (character.choices or {}).get("spellcasting"):
        spell_summary = format_spellcasting_detail(character)
    from jdr_engine.rules.derived_stats import get_class_saving_throw_proficiencies

    save_lines = build_saving_throws(
        modifiers,
        proficient_abilities=get_class_saving_throw_proficiencies(
            engine, character.class_id
        ),
        proficiency_bonus=proficiency,
    )
    saving_display = tuple(line.format_display() for line in save_lines)

    skill_ids = collect_proficient_skills(character, engine)
    skill_labels = tuple(skill_label_fr(sid) for sid in skill_ids)

    hit_dice_remaining, hit_dice_total = read_hit_dice(character)

    spec_id, spec_label = resolve_specialization_label(
        character.choices, engine, locale=locale
    )
    style_id, style_label = resolve_fighting_style_label(
        character.choices, engine, locale=locale
    )

    traits = resolve_race_trait_labels(character, engine, locale=locale)
    trait_ids = traits  # labels utilisés pour affichage ; ids détaillés via resolve_race_traits si besoin
    trait_names = traits

    damage_resistances = format_resistances_display(get_damage_resistances(character))
    innate_spells_text = format_innate_spells_display(character, engine, locale=locale)

    from jdr_engine.rules.class_features.display import build_class_features_display

    class_features_lines = build_class_features_display(
        character, engine, locale=locale
    )

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
        initiative=initiative,
        saving_throws=saving_display,
        proficient_skill_labels=skill_labels,
        hit_dice_remaining=hit_dice_remaining,
        hit_dice_total=hit_dice_total,
        specialization_id=spec_id,
        specialization_label=spec_label,
        fighting_style_id=style_id,
        fighting_style_label=style_label,
        armor_proficiencies_text=format_armor_proficiencies(
            engine, character.class_id, bonus=armor_bonus
        ),
        weapon_proficiencies_text=format_weapon_proficiencies(engine, character.class_id),
        spellcasting_summary=spell_summary,
        trait_ids=trait_ids,
        trait_names=trait_names,
        damage_resistances=damage_resistances,
        innate_spells_text=innate_spells_text,
        class_features_lines=class_features_lines,
        xp=character.xp,
        image_url=character.image_url,
    )
