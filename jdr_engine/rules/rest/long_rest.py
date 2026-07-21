# jdr_engine/rules/rest/long_rest.py
"""Repos long — SRD 2014."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.class_features.barbarian import end_rage, rage_active
from jdr_engine.rules.class_features.fighter import reset_short_rest_features
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.rest.state import (
    get_rest_state,
    hit_dice_regain_amount,
    hit_dice_remaining,
    hit_dice_total,
    sync_hit_dice_total,
)
from jdr_engine.rules.racial.features import reset_racial_features_on_long_rest
from jdr_engine.rules.spellcasting.state import format_slots_display, reset_spell_slots


@dataclass(frozen=True)
class LongRestResult:
    character_name: str
    hp_before: int
    hp_after: int
    hit_dice_before: int
    hit_dice_after: int
    hit_dice_regained: int
    slots_text: str
    prepared_rechoice_pending: bool = False


def apply_long_rest(
    character: Character,
    engine: RuleEngine,
) -> tuple[Character, LongRestResult]:
    """
    Repos long (8 h) — SRD 2014 :
    PV max, récupère des dés de vie, restaure les emplacements.
    """
    character = sync_hit_dice_total(character)

    from jdr_engine.rules.calculator import build_character_sheet

    sheet = build_character_sheet(character, engine)
    hp_max = sheet.hp_max
    hp_before = character.hp_current if character.hp_current is not None else hp_max
    hp_before = min(hp_before, hp_max)

    dice_before = hit_dice_remaining(character)
    total = hit_dice_total(character)
    regain = hit_dice_regain_amount(total)
    dice_after = min(total, dice_before + regain)

    if rage_active(character.choices or {}):
        character.choices = end_rage(character.choices or {})

    from jdr_engine.rules.class_features.barbarian import reset_rage_uses_on_long_rest

    character.choices = reset_rage_uses_on_long_rest(
        character.choices or {},
        level=character.level,
    )

    character.choices = reset_short_rest_features(character.choices or {})

    if character.class_id == "monk":
        from jdr_engine.rules.class_features.monk import reset_ki_points

        character.choices = reset_ki_points(
            character.choices or {}, level=character.level
        )

    if character.class_id == "paladin":
        from jdr_engine.rules.class_features.paladin import (
            reset_channel_divinity_on_short_rest,
            reset_divine_sense_on_long_rest,
            reset_lay_on_hands_on_long_rest,
        )

        cha_score = sheet.ability_scores.get("cha", 10)
        character.choices = reset_divine_sense_on_long_rest(
            character.choices or {}, cha_score=cha_score
        )
        character.choices = reset_lay_on_hands_on_long_rest(
            character.choices or {}, level=character.level
        )
        character.choices = reset_channel_divinity_on_short_rest(
            character.choices or {}, level=character.level
        )

    if character.class_id == "bard":
        from jdr_engine.rules.class_features.bard import reset_bardic_inspiration_on_long_rest

        cha_score = sheet.ability_scores.get("cha", 10)
        character.choices = reset_bardic_inspiration_on_long_rest(
            character.choices or {}, cha_score=cha_score
        )

    if character.class_id == "cleric":
        from jdr_engine.rules.class_features.cleric import reset_preserve_life_on_long_rest

        character.choices = reset_preserve_life_on_long_rest(
            character.choices or {}, level=character.level
        )

    if character.class_id == "wizard":
        from jdr_engine.rules.class_features.wizard import reset_arcane_recovery_on_long_rest

        character.choices = reset_arcane_recovery_on_long_rest(
            character.choices or {}
        )

    if character.class_id == "sorcerer":
        from jdr_engine.rules.class_features.sorcerer import reset_sorcery_points_on_long_rest

        character.choices = reset_sorcery_points_on_long_rest(
            character.choices or {}, level=character.level
        )

    if character.class_id == "druid":
        from jdr_engine.rules.class_features.druid import (
            reset_natural_recovery_on_long_rest,
            reset_wild_shape_on_short_or_long_rest,
        )

        character.choices = reset_wild_shape_on_short_or_long_rest(
            character.choices or {}, level=character.level
        )
        character.choices = reset_natural_recovery_on_long_rest(
            character.choices or {}, level=character.level
        )

    character = reset_racial_features_on_long_rest(character)
    character = reset_spell_slots(character)

    from jdr_engine.rules.spellcasting.prepared_choice import (
        mark_prepared_rechoice_pending,
        requires_prepared_rechoice_class,
    )

    rechoice_pending = False
    if requires_prepared_rechoice_class(character.class_id):
        character = mark_prepared_rechoice_pending(character, pending=True)
        rechoice_pending = True

    character.hp_max = hp_max
    character.hp_current = hp_max

    state = get_rest_state(character)
    state["hit_dice_remaining"] = dice_after
    choices = dict(character.choices or {})
    choices["rest"] = state
    character.choices = choices

    slots_text = format_slots_display(character)
    result = LongRestResult(
        character_name=character.name,
        hp_before=hp_before,
        hp_after=hp_max,
        hit_dice_before=dice_before,
        hit_dice_after=dice_after,
        hit_dice_regained=dice_after - dice_before,
        slots_text=slots_text,
        prepared_rechoice_pending=rechoice_pending,
    )
    return character, result
