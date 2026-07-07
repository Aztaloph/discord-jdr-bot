# jdr_engine/rules/character_creation/finalize.py
"""Assemblage final d'un personnage niveau 1 — compatible moteur de sorts."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import (
    AbilityScores,
    DEFAULT_ABILITY_IDS,
    ability_modifier,
)
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.character_creation.class_choices import (
    CreationChoiceError,
    validate_cleric_domain,
    validate_expertise_skills,
    validate_eldritch_invocations,
    validate_fighting_style_at_level,
    validate_lore_bonus_skills,
    validate_metamagic_options,
    validate_pact_boon,
    validate_ranger_choices,
    validate_skill_choices,
)
from jdr_engine.rules.character_creation.playable import PLAYABLE_CLASSES, PLAYABLE_RACES
from jdr_engine.rules.character_creation.point_buy import validate_point_buy_scores
from jdr_engine.rules.character_creation.race_choices import validate_race_creation_choices
from jdr_engine.rules.character_creation.starting_spells import (
    build_starting_spellcasting,
    init_half_caster_spellcasting_if_needed,
)
from jdr_engine.rules.character_creation.subclass_choices import (
    requires_subclass_at_level,
    validate_subclass_choice,
)
from jdr_engine.rules.derived_stats import collect_proficient_skills
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.racial.resolve import build_tiefling_innate_spells
from jdr_engine.rules.spellcasting.spells_catalog import SUPPORTED_SPELLCASTING_CLASSES


def has_playable_subclass(class_id: str, engine: RuleEngine) -> bool:
    """True si une sous-classe doit être choisie à la création (niv. 1)."""
    from jdr_engine.rules.character_creation.class_choices import (
        requires_domain_at_creation,
        requires_patron_at_creation,
        requires_sorcerous_origin_at_creation,
    )

    return (
        requires_domain_at_creation(engine, class_id)
        or requires_sorcerous_origin_at_creation(engine, class_id)
        or requires_patron_at_creation(engine, class_id)
    )


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
    expertise_skills: list[str] | tuple[str, ...] | None = None,
    specialization: str | None = None,
    fighting_style: str | None = None,
    totem_spirit: str | None = None,
    favored_enemy_type: str | None = None,
    favored_terrain: str | None = None,
    lore_bonus_skills: list[str] | tuple[str, ...] | None = None,
    sorcerer_dragon_type: str | None = None,
    druid_land_terrain: str | None = None,
    metamagic_options: list[str] | tuple[str, ...] | None = None,
    eldritch_invocations: list[str] | tuple[str, ...] | None = None,
    pact_boon: str | None = None,
    draconic_ancestry: str | None = None,
    racial_ability_bonuses: list[str] | tuple[str, ...] | None = None,
    racial_skills: list[str] | tuple[str, ...] | None = None,
) -> Character:
    """
    Construit un Character prêt pour SQLite et le moteur de sorts.

    ``base_scores`` : scores avant bonus raciaux (point buy 8–15).
    ``level`` : 1 par défaut ; 2–3 autorisé pour tests (sous-classe requise au niv. 3).
    """
    if class_id not in PLAYABLE_CLASSES:
        raise ValueError(f"Classe non jouable : {class_id!r}")
    if race_id not in PLAYABLE_RACES:
        raise ValueError(f"Race non jouable : {race_id!r}")
    if level < 1 or level > 3:
        raise ValueError("Création limitée aux niveaux 1 à 3.")

    validate_point_buy_scores(base_scores)

    validated_meta: tuple[str, ...] = ()
    try:
        validated_skills = validate_skill_choices(engine, class_id, skills)
        domain = validate_cleric_domain(engine, class_id, specialization)
        style = validate_fighting_style_at_level(
            engine, class_id, fighting_style, character_level=level
        )
        enemy_type, terrain = validate_ranger_choices(
            engine, class_id, favored_enemy_type, favored_terrain
        )
        if requires_subclass_at_level(engine, class_id, level):
            spec_id, sub_id, sub_key = validate_subclass_choice(
                engine,
                class_id,
                specialization,
                totem_spirit=totem_spirit,
                subchoice_value=sorcerer_dragon_type or druid_land_terrain,
                character_level=level,
            )
        else:
            spec_id, sub_id, sub_key = None, None, None
            if specialization:
                from jdr_engine.rules.character_creation.subclass_choices import (
                    get_subclass_choice_config,
                )

                cfg = get_subclass_choice_config(engine, class_id)
                if cfg is not None and level < cfg.level:
                    raise CreationChoiceError(
                        f"Sous-classe disponible à partir du niveau {cfg.level}."
                    )
        validated_meta = validate_metamagic_options(
            engine, class_id, metamagic_options, level=level
        )
        validated_invocations = validate_eldritch_invocations(
            engine, class_id, eldritch_invocations, level=level
        )
        validated_pact_boon = validate_pact_boon(
            engine, class_id, pact_boon, level=level
        )
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
        wis_mod = ability_modifier(scores.get("wis", 10))
        int_mod = ability_modifier(scores.get("int", 10))
        casting_mod = int_mod if class_id == "wizard" else wis_mod
        sc = build_starting_spellcasting(
            class_id,
            level=level,
            casting_ability_mod=casting_mod,
            domain_id=domain if class_id == "cleric" else None,
        )
        if sc:
            choices["spellcasting"] = sc

    if enemy_type:
        choices["favored_enemy_type"] = enemy_type
    if terrain:
        choices["favored_terrain"] = terrain

    if domain:
        choices["specialization"] = domain
    elif spec_id:
        choices["specialization"] = spec_id
        if sub_id and sub_key:
            choices[sub_key] = sub_id

    if style:
        choices["fighting_style"] = style

    choices.update(racial_choices)

    if race_id == "tiefling":
        choices["innate_spells"] = build_tiefling_innate_spells()

    choices["rest"] = {
        "hit_dice_total": level,
        "hit_dice_remaining": level,
    }

    if class_id == "barbarian":
        from jdr_engine.rules.class_features.barbarian import init_rage_uses

        choices = init_rage_uses(choices, level=level)

    if class_id == "paladin":
        from jdr_engine.rules.class_features.paladin import init_paladin_features

        cha_score = scores.get("cha", 10)
        choices = init_paladin_features(choices, level=level, cha_score=cha_score)

    if class_id == "bard":
        from jdr_engine.rules.class_features.bard import init_bard_features

        choices = init_bard_features(
            choices, level=level, cha_score=scores.get("cha", 10)
        )

    if class_id == "cleric":
        from jdr_engine.rules.class_features.cleric import init_cleric_features

        choices = init_cleric_features(choices, level=level)

    if class_id == "wizard":
        from jdr_engine.rules.class_features.wizard import init_wizard_features

        choices = init_wizard_features(choices, level=level)

    if class_id == "sorcerer":
        from jdr_engine.rules.class_features.sorcerer import init_sorcerer_features

        choices = init_sorcerer_features(choices, level=level)

    if class_id == "druid":
        from jdr_engine.rules.class_features.druid import init_druid_features

        choices = init_druid_features(choices, level=level)

    if validated_meta:
        choices["metamagic_options"] = list(validated_meta)

    if validated_invocations:
        choices["eldritch_invocations"] = list(validated_invocations)

    if validated_pact_boon:
        choices["pact_boon"] = validated_pact_boon

    choices = init_half_caster_spellcasting_if_needed(choices, class_id, level=level)

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

    try:
        spec_for_lore = domain or spec_id
        validated_lore = validate_lore_bonus_skills(
            engine,
            class_id,
            spec_for_lore,
            lore_bonus_skills,
            level=level,
        )
    except CreationChoiceError as exc:
        raise ValueError(str(exc)) from exc

    if validated_lore:
        character.choices["lore_bonus_skills"] = list(validated_lore)

    try:
        proficient = collect_proficient_skills(character, engine)
        validated_expertise = validate_expertise_skills(
            engine,
            class_id,
            expertise_skills,
            proficient,
            level=level,
        )
    except CreationChoiceError as exc:
        raise ValueError(str(exc)) from exc

    if validated_expertise:
        character.choices["expertise_skills"] = list(validated_expertise)

    if class_id == "monk" and level >= 2:
        from jdr_engine.rules.class_features.monk import init_ki_points

        character.choices = init_ki_points(character.choices or {}, level=level)

    sheet = build_character_sheet(character, engine)
    character.hp_max = sheet.hp_max
    character.hp_current = sheet.hp_max
    return character
