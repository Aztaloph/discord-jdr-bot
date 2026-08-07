# interfaces/api/combat_attack.py
"""Construction requête jet d'attaque API → ``D20RollRequest`` moteur."""
from __future__ import annotations

from jdr_engine.dice.d20 import D20RollRequest
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.character_sheet import CharacterSheet
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.engine import RuleEngine


def build_weapon_attack_request(
    character: Character,
    engine: RuleEngine,
    *,
    melee_weapon: bool,
    ranged_weapon: bool,
    locale: str = "fr",
) -> D20RollRequest:
    """
    Dérive le contexte de jet d'attaque depuis la fiche calculée.

    Le client fournit le contexte de portée ; modificateurs et maîtrise viennent
    du moteur (pas saisis librement par le client).
    """
    sheet = build_character_sheet(character, engine, locale=locale)
    ability = "dex" if ranged_weapon else "str"
    ability_modifier = sheet.ability_modifiers[ability]
    is_proficient = bool(sheet.weapon_proficiencies)
    return D20RollRequest(
        roll_type="attack",
        ability_modifier=ability_modifier,
        proficiency_bonus=sheet.proficiency_bonus,
        is_proficient=is_proficient,
        ability=ability,
        melee_weapon=melee_weapon,
        ranged_weapon=ranged_weapon,
    )
