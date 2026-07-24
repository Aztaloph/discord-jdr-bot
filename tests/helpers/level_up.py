# tests/helpers/level_up.py
"""Helpers montée de niveau — tests progression full caster (Lot A2)."""
from __future__ import annotations

from jdr_engine.rules.character_creation.finalize import finalize_new_character
from jdr_engine.rules.character_progression import apply_level_up
from jdr_engine.rules.character_progression.asi import ASI_LEVELS
from jdr_engine.rules.engine import RuleEngine

from tests.helpers.creation import wizard_creation_kwargs

# ASI par palier — évite de repousser INT au-delà du cap effectif 20 (humain +1).
WIZARD_ASI_CHOICES: dict[int, dict[str, int]] = {
    4: {"int": 2},
    8: {"int": 2},
    12: {"wis": 2},
    16: {"con": 2},
    19: {"dex": 2},
}


def level_up_wizard(
    character,
    engine: RuleEngine,
    target_level: int,
    *,
    asi_choices: dict[int, dict[str, int]] | None = None,
):
    """Monte un magicien existant jusqu'à ``target_level`` (ASI aux paliers SRD)."""
    choices = asi_choices if asi_choices is not None else WIZARD_ASI_CHOICES
    char = character
    while char.level < target_level:
        next_level = char.level + 1
        kwargs: dict = {}
        if next_level in ASI_LEVELS:
            kwargs["asi_choice"] = choices[next_level]
        char, _ = apply_level_up(char, engine, **kwargs)
    return char


def wizard_at_level(
    engine: RuleEngine,
    target_level: int,
    *,
    asi_choices: dict[int, dict[str, int]] | None = None,
    **creation_overrides,
):
    """Crée un magicien évocation et le monte jusqu'à ``target_level``."""
    if target_level < 1:
        raise ValueError("target_level >= 1")
    kwargs = wizard_creation_kwargs(level=min(3, target_level), **creation_overrides)
    if target_level >= 2 and "specialization" not in creation_overrides:
        kwargs["specialization"] = "evocation"
    char = finalize_new_character(
        owner_id="1",
        guild_id="900",
        name="Merlin",
        engine=engine,
        **kwargs,
    )
    if target_level <= char.level:
        return char
    if char.level == 1 and target_level >= 2:
        char, _ = apply_level_up(char, engine, subclass="evocation")
    if char.level == 2 and target_level >= 3:
        char, _ = apply_level_up(char, engine)
    if target_level <= char.level:
        return char
    return level_up_wizard(char, engine, target_level, asi_choices=asi_choices)
