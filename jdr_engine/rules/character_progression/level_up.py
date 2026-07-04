# jdr_engine/rules/character_progression/level_up.py
"""Montée de niveau SRD 2014 — Lot 2 (Magicien & Clerc, niv. 2–3)."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.calculator import build_character_sheet, parse_hit_die
from jdr_engine.rules.character_creation.playable import PLAYABLE_CLASSES
from jdr_engine.rules.derived_stats import calculate_hp_gain_per_level
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.rest.state import hit_dice_remaining, hit_dice_total, sync_hit_dice_total
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots

# Lot 2 : progression limitée aux niveaux 2 et 3.
MAX_LEVEL_LOT2 = 3

# TODO (Lot ASI niv.4) : à new_level in ASI_LEVELS, proposer le composant
# ``PointBuyDistributionView`` (interfaces.discord.components.point_buy_distribution)
# pour l'augmentation de caractéristique SRD (+2 à une carac ou +1 à deux carac).
# ASI_LEVELS_SRD: tuple[int, ...] = (4, 8, 12, 16, 19)


class LevelUpError(Exception):
    """Montée de niveau impossible (niveau max, classe non supportée, etc.)."""


@dataclass(frozen=True)
class LevelUpResult:
    character_name: str
    class_id: str
    old_level: int
    new_level: int
    hp_before: int
    hp_after: int
    hp_max_before: int
    hp_max_after: int
    hp_gain: int
    hit_dice_before: int
    hit_dice_after: int
    slots_max_before: str
    slots_max_after: str


def _format_max_slots(class_id: str, level: int) -> str:
    max_slots = get_max_spell_slots(class_id, level)
    if not max_slots:
        return "—"
    return ", ".join(f"niv.{lvl}: {count}" for lvl, count in sorted(max_slots.items()))


def apply_level_up(
    character: Character,
    engine: RuleEngine,
) -> tuple[Character, LevelUpResult]:
    """
    Monte le personnage d'un niveau (SRD 2014, Lot 2).

    Modifie : ``level``, ``hp_max``, ``hp_current``, ``choices.rest`` (dés de vie).
    Les emplacements max sont dérivés du niveau via ``get_max_spell_slots`` (pas de mutation).
    Les sorts connus ne changent pas (préparation = lot ultérieur).
    """
    if character.class_id not in PLAYABLE_CLASSES:
        raise LevelUpError(
            f"Montée de niveau non supportée pour la classe « {character.class_id} » "
            f"(Lot 2 : Magicien et Clerc uniquement)."
        )
    if character.level >= MAX_LEVEL_LOT2:
        raise LevelUpError(
            f"**{character.name}** est déjà au niveau maximum pour ce lot (niv. {MAX_LEVEL_LOT2})."
        )

    old_level = character.level
    new_level = old_level + 1

    sheet = build_character_sheet(character, engine)
    hit_die = engine.get_class_hit_die(character.class_id)
    if not hit_die:
        raise LevelUpError(f"Dé de vie introuvable pour {character.class_id!r}.")
    hit_die_faces = parse_hit_die(hit_die)
    con_mod = sheet.ability_modifiers.get("con", 0)

    hp_before = sheet.hp_current
    hp_max_before = sheet.hp_max
    hp_gain = calculate_hp_gain_per_level(hit_die_faces, con_mod)
    hp_max_after = hp_max_before + hp_gain
    hp_after = min(hp_before + hp_gain, hp_max_after)

    dice_before = hit_dice_remaining(character)
    slots_max_before = _format_max_slots(character.class_id, old_level)

    character.level = new_level
    character.hp_max = hp_max_after
    character.hp_current = hp_after
    character = sync_hit_dice_total(character)

    dice_after = hit_dice_total(character)
    slots_max_after = _format_max_slots(character.class_id, new_level)

    result = LevelUpResult(
        character_name=character.name,
        class_id=character.class_id,
        old_level=old_level,
        new_level=new_level,
        hp_before=hp_before,
        hp_after=hp_after,
        hp_max_before=hp_max_before,
        hp_max_after=hp_max_after,
        hp_gain=hp_gain,
        hit_dice_before=dice_before,
        hit_dice_after=dice_after,
        slots_max_before=slots_max_before,
        slots_max_after=slots_max_after,
    )
    return character, result
