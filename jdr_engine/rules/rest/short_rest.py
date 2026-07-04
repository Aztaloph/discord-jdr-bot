# jdr_engine/rules/rest/short_rest.py
"""Repos court — SRD 2014."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.calculator import build_character_sheet, parse_hit_die
from jdr_engine.rules.class_features.fighter import reset_short_rest_features
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.rest.errors import RestError
from jdr_engine.rules.rest.state import (
    get_rest_state,
    hit_dice_remaining,
    sync_hit_dice_total,
)

RandInt = Callable[[int, int], int]


@dataclass(frozen=True)
class HitDieRoll:
    faces: int
    con_modifier: int
    roll_value: int
    healing: int

    @property
    def label(self) -> str:
        mod = self.con_modifier
        mod_str = f"{mod:+d}" if mod else ""
        return f"d{self.faces}{mod_str} → **{self.healing}** PV (jet {self.roll_value})"


@dataclass(frozen=True)
class ShortRestResult:
    character_name: str
    hp_before: int
    hp_after: int
    dice_spent: int
    hit_dice_remaining: int
    rolls: tuple[HitDieRoll, ...]


def apply_short_rest(
    character: Character,
    engine: RuleEngine,
    dice_to_spend: int,
    *,
    rng: RandInt | None = None,
) -> tuple[Character, ShortRestResult]:
    """
    Repos court (1 h) — dépense volontairement des dés de vie.
    Chaque dé : dé de vie de la classe + mod CON (minimum 0 PV récupérés).
    """
    if dice_to_spend < 0:
        raise RestError("Le nombre de dés doit être positif ou nul.")

    character = sync_hit_dice_total(character)
    available = hit_dice_remaining(character)

    if dice_to_spend > available:
        raise RestError(
            f"Dés de vie insuffisants : **{available}** disponible(s), "
            f"**{dice_to_spend}** demandé(s)."
        )

    sheet = build_character_sheet(character, engine)
    hp_max = sheet.hp_max
    hp_before = character.hp_current if character.hp_current is not None else hp_max
    hp_before = min(hp_before, hp_max)

    hit_die_faces = parse_hit_die(sheet.hit_die)
    con_mod = sheet.ability_modifiers.get("con", 0)

    rolls: list[HitDieRoll] = []
    hp_current = hp_before

    roll_fn = rng
    for _ in range(dice_to_spend):
        if roll_fn is not None:
            die_value = roll_fn(1, hit_die_faces)
        else:
            import random

            die_value = random.randint(1, hit_die_faces)
        raw_healing = max(0, die_value + con_mod)
        before_roll = hp_current
        if hp_current < hp_max:
            hp_current = min(hp_max, hp_current + raw_healing)
        actual_healing = hp_current - before_roll
        rolls.append(
            HitDieRoll(
                faces=hit_die_faces,
                con_modifier=con_mod,
                roll_value=die_value,
                healing=actual_healing,
            )
        )

    dice_spent = len(rolls)
    remaining = available - dice_spent

    character.choices = reset_short_rest_features(character.choices or {})
    character.hp_current = hp_current

    state = get_rest_state(character)
    state["hit_dice_remaining"] = remaining
    choices = dict(character.choices or {})
    choices["rest"] = state
    character.choices = choices

    result = ShortRestResult(
        character_name=character.name,
        hp_before=hp_before,
        hp_after=hp_current,
        dice_spent=dice_spent,
        hit_dice_remaining=remaining,
        rolls=tuple(rolls),
    )
    return character, result
