# jdr_engine/application/dto/output_serializers.py
"""
DTO de sortie — conversions objets de résultat → dictionnaires JSON-sérialisables.

Principe directeur : **données uniquement**. Les champs de texte pré-formaté
destinés à l'affichage (``display_lines``, ``slots_text``, ``spellcasting_summary``,
``saving_throws`` en chaînes, ``modifier_breakdown``, etc.) ne sont **jamais**
exposés ici — ils restent en place pour les formateurs Discord. Chaque
information qu'ils portent est exposée via son équivalent structuré
(``saving_throw_entries``, ``SpellcastingView``, ``slots_max``/``slots_remaining``…).

``updated_character`` n'est jamais exposé : c'est un détail de persistance,
géré par la couche appelante (API / handler).

Conventions de conversion :
- ``tuple`` → ``list`` ;
- ``Literal`` → ``str`` ;
- clés ``int`` de dictionnaires (niveaux d'emplacements) → ``str`` ;
- objets imbriqués convertis récursivement.

Dette assumée (lot DTO/API) : les **compteurs de ressources de classe**
(rage, ki, second souffle, inspiration bardique…) n'ont aucun équivalent
structuré — ils ne vivent que dans ``class_features_lines`` (texte), assemblés
par ``jdr_engine/rules/class_features/display.py`` depuis des fonctions éparses.
``class_features`` n'expose ici que les ids + libellés des aptitudes. Les
compteurs relèvent de la phase combat et mériteront une conception dédiée.
"""
from __future__ import annotations

from typing import Any

from jdr_engine.dice.d20 import D20RollRequest, D20RollResult
from jdr_engine.domain.character.character_sheet import (
    CharacterSheet,
    SpellcastingView,
)
from jdr_engine.rules.rest.long_rest import LongRestResult
from jdr_engine.rules.rest.short_rest import HitDieRoll, ShortRestResult
from jdr_engine.rules.spellcasting.cast import SpellAttackRoll, SpellCastResult

__all__ = [
    "character_sheet_to_dict",
    "spell_cast_result_to_dict",
    "short_rest_result_to_dict",
    "long_rest_result_to_dict",
]


def _slots_to_dict(slots: dict[int, int]) -> dict[str, int]:
    """Clés int (niveau d'emplacement) → str, pour JSON."""
    return {str(level): int(count) for level, count in sorted(slots.items())}


def _spellcasting_view_to_dict(view: SpellcastingView) -> dict[str, Any]:
    concentration: dict[str, Any] | None = None
    if view.concentration_spell_id or view.concentration_spell_name:
        concentration = {
            "spell_id": view.concentration_spell_id,
            "spell_name": view.concentration_spell_name,
        }
    return {
        "ability": view.ability,
        "pact_magic": view.pact_magic,
        "slots_max": _slots_to_dict(view.slots_max),
        "slots_remaining": _slots_to_dict(view.slots_remaining),
        "concentration": concentration,
        "cantrips_known": list(view.cantrips_known),
        "spells_prepared": list(view.spells_prepared),
        "spells_known": list(view.spells_known),
        "spellbook": list(view.spellbook),
        "domain_spells": list(view.domain_spells),
    }


def character_sheet_to_dict(sheet: CharacterSheet) -> dict[str, Any]:
    """
    Fiche personnage → dict JSON-sérialisable.

    Expose les composants, pas les ``@property`` d'assemblage
    (``class_display``, ``hit_dice_display``). Exclus : ``saving_throws``
    (chaînes), ``proficient_skill_labels``, ``armor_proficiencies_text``,
    ``weapon_proficiencies_text``, ``spellcasting_summary``,
    ``class_features_lines``, ``damage_resistances`` (chaîne agrégée),
    ``innate_spells_text``, ``trait_ids`` (contient des libellés — bug connu,
    seul ``trait_names`` est exposé).
    """
    return {
        "character_id": sheet.character_id,
        "name": sheet.name,
        "owner_id": sheet.owner_id,
        "ruleset_id": sheet.ruleset_id,
        "race_id": sheet.race_id,
        "race_name": sheet.race_name,
        "class_id": sheet.class_id,
        "class_name": sheet.class_name,
        "level": sheet.level,
        "xp": sheet.xp,
        "image_url": sheet.image_url,
        "ability_scores_base": dict(sheet.ability_scores_base),
        "ability_scores": dict(sheet.ability_scores),
        "ability_modifiers": dict(sheet.ability_modifiers),
        "proficiency_bonus": sheet.proficiency_bonus,
        "hit_die": sheet.hit_die,
        "hp_max": sheet.hp_max,
        "hp_current": sheet.hp_current,
        "ac": sheet.ac,
        "speed": sheet.speed,
        "initiative": sheet.initiative,
        "hit_dice_remaining": sheet.hit_dice_remaining,
        "hit_dice_total": sheet.hit_dice_total,
        "specialization_id": sheet.specialization_id,
        "specialization_label": sheet.specialization_label,
        "fighting_style_id": sheet.fighting_style_id,
        "fighting_style_label": sheet.fighting_style_label,
        "saving_throws": [
            {
                "ability_id": entry.ability_id,
                "modifier": entry.modifier,
                "proficient": entry.proficient,
            }
            for entry in sheet.saving_throw_entries
        ],
        "proficient_skill_ids": list(sheet.proficient_skill_ids),
        "armor_proficiencies": list(sheet.armor_proficiencies),
        "weapon_proficiencies": list(sheet.weapon_proficiencies),
        "damage_resistances": list(sheet.damage_resistance_ids),
        "trait_names": list(sheet.trait_names),
        "innate_spells": [
            {
                "spell_id": entry.spell_id,
                "usage": entry.usage,
                "min_level": entry.min_level,
            }
            for entry in sheet.innate_spells
        ],
        "class_features": [
            {"feature_id": ref.feature_id, "name": ref.name}
            for ref in sheet.class_features
        ],
        "spellcasting": (
            _spellcasting_view_to_dict(sheet.spellcasting)
            if sheet.spellcasting is not None
            else None
        ),
    }


def _d20_request_to_dict(request: D20RollRequest) -> dict[str, Any]:
    return {
        "roll_type": str(request.roll_type),
        "ability_modifier": request.ability_modifier,
        "proficiency_bonus": request.proficiency_bonus,
        "is_proficient": request.is_proficient,
        "ability": request.ability,
        "skill": request.skill,
        "save_versus_condition": request.save_versus_condition,
        "base_mode": str(request.base_mode),
        "tracking": request.tracking,
        "recalling_favored_enemy_info": request.recalling_favored_enemy_info,
        "favored_terrain_related": request.favored_terrain_related,
        "rage_active": request.rage_active,
        "reckless_attack": request.reckless_attack,
        "target_reckless": request.target_reckless,
        "visible_effect": request.visible_effect,
        "ranged_weapon": request.ranged_weapon,
        "melee_weapon": request.melee_weapon,
        "finesse_weapon": request.finesse_weapon,
        "str_melee_attack": request.str_melee_attack,
        "expertise_skills": list(request.expertise_skills),
    }


def _d20_result_to_dict(result: D20RollResult) -> dict[str, Any]:
    """Exclu : ``modifier_breakdown`` (texte) — le total ``modifier`` suffit."""
    return {
        "request": _d20_request_to_dict(result.request),
        "rolls": list(result.rolls),
        "is_kept": list(result.is_kept),
        "kept_value": result.kept_value,
        "mode": str(result.mode),
        "modifier": result.modifier,
        "total": result.total,
        "natural_20": result.natural_20,
        "natural_1": result.natural_1,
        "applied_effects": list(result.applied_effects),
        "rerolled": result.rerolled,
    }


def _spell_attack_roll_to_dict(atk: SpellAttackRoll) -> dict[str, Any]:
    return {
        "index": atk.index,
        "damage_total": atk.damage_total,
        "damage_notation": atk.damage_notation,
        "damage_rolls": list(atk.damage_rolls),
        "attack_bonus": atk.attack_bonus,
        "auto_hit": atk.auto_hit,
        "d20": (
            _d20_result_to_dict(atk.d20_result)
            if atk.d20_result is not None
            else None
        ),
    }


def spell_cast_result_to_dict(result: SpellCastResult) -> dict[str, Any]:
    """
    Résultat de lancement de sort → dict JSON-sérialisable.

    Exclus : ``display_lines`` (texte) et ``updated_character`` (persistance).
    ``buff_text`` / ``utility_text`` sont exposés : contenu de règle localisé
    issu du YAML, pas de la mise en forme générée.
    """
    return {
        "spell_id": result.spell_id,
        "spell_name": result.spell_name,
        "spell_level": result.spell_level,
        "school": result.school,
        "casting_time": result.casting_time,
        "range_text": result.range_text,
        "duration": result.duration,
        "effect_type": result.effect_type,
        "attack_bonus": result.attack_bonus,
        "save_dc": result.save_dc,
        "save_ability": result.save_ability,
        "attack_rolls": [
            _spell_attack_roll_to_dict(atk) for atk in result.attack_rolls
        ],
        "damage_total": result.damage_total,
        "damage_notation": result.damage_notation,
        "damage_rolls": list(result.damage_rolls),
        "damage_type": result.damage_type,
        "half_on_save": result.half_on_save,
        "healing_total": result.healing_total,
        "healing_applied": result.healing_applied,
        "healing_rolls": list(result.healing_rolls),
        "healing_capped": result.healing_capped,
        "hp_before": result.hp_before,
        "hp_after": result.hp_after,
        "hp_max": result.hp_max,
        "utility_text": result.utility_text,
        "buff_text": result.buff_text,
        "concentration": result.concentration,
        "interrupted_concentration": result.interrupted_concentration,
        "slot_consumed_level": result.slot_consumed_level,
        "slots_max": _slots_to_dict(result.slots_max),
        "slots_remaining": _slots_to_dict(result.slots_remaining),
        "metamagic_options": [
            {"metamagic_id": option.metamagic_id, "cost": option.cost}
            for option in result.metamagic_options
        ],
    }


def _hit_die_roll_to_dict(roll: HitDieRoll) -> dict[str, Any]:
    """Exclu : la ``@property label`` — recomposable depuis les composants."""
    return {
        "faces": roll.faces,
        "con_modifier": roll.con_modifier,
        "roll_value": roll.roll_value,
        "healing": roll.healing,
    }


def short_rest_result_to_dict(result: ShortRestResult) -> dict[str, Any]:
    """Résultat de repos court → dict JSON-sérialisable."""
    return {
        "character_name": result.character_name,
        "hp_before": result.hp_before,
        "hp_after": result.hp_after,
        "dice_spent": result.dice_spent,
        "hit_dice_remaining": result.hit_dice_remaining,
        "rolls": [_hit_die_roll_to_dict(roll) for roll in result.rolls],
    }


def long_rest_result_to_dict(result: LongRestResult) -> dict[str, Any]:
    """
    Résultat de repos long → dict JSON-sérialisable.

    Exclu : ``slots_text`` (texte) — remplacé par ``slots_max`` /
    ``slots_remaining`` structurés.
    """
    return {
        "character_name": result.character_name,
        "hp_before": result.hp_before,
        "hp_after": result.hp_after,
        "hit_dice_before": result.hit_dice_before,
        "hit_dice_after": result.hit_dice_after,
        "hit_dice_regained": result.hit_dice_regained,
        "prepared_rechoice_pending": result.prepared_rechoice_pending,
        "slots_max": _slots_to_dict(result.slots_max),
        "slots_remaining": _slots_to_dict(result.slots_remaining),
    }
