# jdr_engine/rules/combat/spell_resolution.py
"""Résolution de sorts en combat — lot C3b (attaque, sauvegarde, DD)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from jdr_engine.dice.d20 import D20Mode, D20RollRequest
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.cast import (
    SpellCastError,
    _get_effects,
    _primary_effect,
    _resolve_damage_notation,
    _save_spec,
    _spellcasting_ability,
    get_spellcasting_stats,
)

EffectType = Literal["spell_attack", "saving_throw", "buff"]


@dataclass(frozen=True)
class CombatSpellEffect:
    """Effet principal d'un sort pour le combat."""

    spell_id: str
    spell_name: str
    spell_level: int
    effect_type: EffectType
    effect: dict[str, Any]
    spell_def: dict[str, Any]
    concentration: bool
    damage_type: str = ""


def load_combat_spell(
    engine: RuleEngine,
    spell_id: str,
    *,
    locale: str = "fr",
) -> CombatSpellEffect:
    """Charge un sort et son effet principal depuis le compendium."""
    entry = engine.get_entity("spell", spell_id)
    if entry is None:
        raise SpellCastError(f"Sort inconnu : {spell_id!r}.")

    spell_def = entry.definition.model_dump()
    effects = _get_effects(spell_def)
    effect = _primary_effect(effects)
    effect_type = str(effect.get("type", ""))
    if effect_type not in ("spell_attack", "saving_throw", "buff"):
        raise SpellCastError(
            f"Sort {spell_id!r} : effet {effect_type!r} non pris en charge en combat (C3b)."
        )

    mechanics = spell_def.get("mechanics", {})
    spell_name = entry.get_name(locale, engine.registry.manifest.default_locale)
    return CombatSpellEffect(
        spell_id=spell_id,
        spell_name=spell_name,
        spell_level=int(mechanics.get("level", 0)),
        effect_type=effect_type,  # type: ignore[arg-type]
        effect=effect,
        spell_def=spell_def,
        concentration=bool(mechanics.get("concentration", False)),
        damage_type=str(effect.get("damage_type", "")),
    )


def compute_spell_save_dc(character: Character, engine: RuleEngine) -> int:
    """DD = 8 + maîtrise + mod caractéristique d'incantation."""
    _ability_mod, _attack_bonus, save_dc = get_spellcasting_stats(character, engine)
    return save_dc


def build_spell_attack_request(
    character: Character,
    engine: RuleEngine,
    *,
    base_mode: D20Mode = "normal",
) -> D20RollRequest:
    """Requête d20 pour attaque de sort — mod incantation + maîtrise."""
    ability_id = _spellcasting_ability(character, engine)
    ability_mod, _attack_bonus, _save_dc = get_spellcasting_stats(character, engine)
    proficiency = engine.get_proficiency_bonus(character.level)
    return D20RollRequest(
        roll_type="attack",
        ability_modifier=ability_mod,
        proficiency_bonus=proficiency,
        is_proficient=True,
        ability=ability_id,
        base_mode=base_mode,
    )


def build_save_request(
    character: Character,
    engine: RuleEngine,
    ability_id: str,
    *,
    base_mode: D20Mode = "normal",
) -> D20RollRequest:
    """Requête d20 pour jet de sauvegarde de la cible."""
    sheet = build_character_sheet(character, engine)
    ability_mod = sheet.ability_modifiers.get(ability_id, 0)
    save_entry = next(
        (entry for entry in sheet.saving_throw_entries if entry.ability_id == ability_id),
        None,
    )
    is_proficient = save_entry.proficient if save_entry is not None else False
    return D20RollRequest(
        roll_type="saving_throw",
        ability_modifier=ability_mod,
        proficiency_bonus=sheet.proficiency_bonus,
        is_proficient=is_proficient,
        ability=ability_id,
        base_mode=base_mode,
    )


def resolve_spell_damage_notation(
    spell: CombatSpellEffect,
    character: Character,
) -> str:
    """Notation de dégâts effective (cantrip scaling inclus)."""
    if spell.effect_type != "spell_attack" and spell.effect_type != "saving_throw":
        raise SpellCastError("Ce sort n'inflige pas de dégâts directs.")
    return _resolve_damage_notation(
        spell.spell_def,
        spell.effect,
        spell_level=spell.spell_level,
        character_level=character.level,
    )


def save_ability_for_spell(spell: CombatSpellEffect) -> str:
    """Identifiant de caractéristique pour le jet de sauvegarde."""
    save_info = _save_spec(spell.effect)
    return str(save_info.get("ability", "dex"))


def half_on_save_for_spell(spell: CombatSpellEffect) -> bool:
    save_info = _save_spec(spell.effect)
    return bool(save_info.get("half_on_save", True))
