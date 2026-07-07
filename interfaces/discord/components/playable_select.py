# interfaces/discord/components/playable_select.py
"""Selects limités aux options réellement jouables."""
from __future__ import annotations

import discord

from jdr_engine.rules.character_creation.playable import PLAYABLE_CLASSES, PLAYABLE_RACES
from jdr_engine.rules.engine import RuleEngine

_CLASS_DESCRIPTIONS_FR: dict[str, str] = {
    "barbarian": "d12 · FOR/CON · martiale",
    "bard": "d8 · CHA · lanceur complet",
    "cleric": "d8 · SAG · lanceur (/sort actif)",
    "druid": "d8 · SAG · lanceur complet",
    "fighter": "d10 · FOR/CON · martiale",
    "monk": "d8 · DEX/SAG · martiale",
    "paladin": "d10 · CHA · demi-lanceur (niv. 2+)",
    "ranger": "d10 · SAG · demi-lanceur (niv. 2+)",
    "rogue": "d8 · DEX · martiale",
    "sorcerer": "d6 · CHA · lanceur complet",
    "warlock": "d8 · CHA · pactisant (Pact Magic)",
    "wizard": "d6 · INT · lanceur (/sort actif)",
}


def playable_class_select_options(
    engine: RuleEngine,
    locale: str = "fr",
) -> list[discord.SelectOption]:
    options: list[discord.SelectOption] = []
    for class_id in PLAYABLE_CLASSES:
        label = engine.get_display_name("class", class_id, locale=locale) or class_id
        description = _CLASS_DESCRIPTIONS_FR.get(class_id, class_id)[:100]
        options.append(
            discord.SelectOption(
                label=label[:100],
                value=class_id,
                description=description,
            )
        )
    return options


def playable_race_select_options(
    engine: RuleEngine,
    locale: str = "fr",
) -> list[discord.SelectOption]:
    options: list[discord.SelectOption] = []
    for race_id in PLAYABLE_RACES:
        label = engine.get_display_name("race", race_id, locale=locale) or race_id
        options.append(
            discord.SelectOption(
                label=label[:100],
                value=race_id,
                description=race_id,
            )
        )
    return options
