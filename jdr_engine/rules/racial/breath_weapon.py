# jdr_engine/rules/racial/breath_weapon.py
"""Souffle draconique — action raciale SRD 2014 (niv. 1-5 : 2d6)."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS, ability_modifier
from jdr_engine.domain.character.character import Character
from jdr_engine.dice import roll
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.racial.draconic_ancestry import get_draconic_ancestry
from jdr_engine.rules.racial.resolve import get_draconic_ancestry_id, get_racial_ability_bonuses

DAMAGE_TYPE_LABELS_FR: dict[str, str] = {
    "acid": "acide",
    "cold": "froid",
    "fire": "feu",
    "lightning": "foudre",
    "poison": "poison",
}


class BreathWeaponError(Exception):
    pass


@dataclass(frozen=True)
class BreathWeaponResult:
    character_name: str
    ancestry_label: str
    damage_type: str
    damage_type_label: str
    shape: str
    area_ft: int
    damage_dice: str
    damage_total: int
    save_dc: int
    con_modifier: int


def breath_weapon_damage_dice(level: int) -> str:
    """SRD 2014 — dégâts du souffle par palier de niveau."""
    if level <= 5:
        return "2d6"
    if level <= 10:
        return "3d6"
    if level <= 15:
        return "4d6"
    return "5d6"


def use_breath_weapon(
    character: Character,
    engine: RuleEngine,
) -> BreathWeaponResult:
    if character.race_id != "dragonborn":
        raise BreathWeaponError("Seul un Drakéide possède un souffle draconique.")

    color_id = get_draconic_ancestry_id(character)
    if not color_id:
        raise BreathWeaponError(
            "Ascendance draconique non définie sur ce personnage."
        )

    ancestry = get_draconic_ancestry(color_id)
    if ancestry is None:
        raise BreathWeaponError(f"Ascendance invalide : {color_id!r}.")

    base_scores = character.ability_scores.with_defaults(DEFAULT_ABILITY_IDS).scores
    racial = get_racial_ability_bonuses(character, engine)
    con_score = base_scores.get("con", 10) + racial.get("con", 0)
    con_mod = ability_modifier(con_score)
    prof = engine.get_proficiency_bonus(character.level)
    save_dc = 8 + con_mod + prof

    dice_expr = breath_weapon_damage_dice(character.level)
    damage_result = roll(dice_expr)
    damage_total = damage_result.total

    shape_label = "ligne" if ancestry.shape == "line" else "cône"
    type_label = DAMAGE_TYPE_LABELS_FR.get(ancestry.damage_type, ancestry.damage_type)

    return BreathWeaponResult(
        character_name=character.name,
        ancestry_label=ancestry.label_fr,
        damage_type=ancestry.damage_type,
        damage_type_label=type_label,
        shape=shape_label,
        area_ft=ancestry.area_ft,
        damage_dice=dice_expr,
        damage_total=damage_total,
        save_dc=save_dc,
        con_modifier=con_mod,
    )
