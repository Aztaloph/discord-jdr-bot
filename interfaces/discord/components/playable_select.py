# interfaces/discord/components/playable_select.py
"""Selects limités aux options réellement jouables."""
from __future__ import annotations

import discord

from jdr_engine.rules.character_creation.playable import PLAYABLE_CLASSES, PLAYABLE_RACES
from jdr_engine.rules.engine import RuleEngine


def playable_class_select_options(
    engine: RuleEngine,
    locale: str = "fr",
) -> list[discord.SelectOption]:
    options: list[discord.SelectOption] = []
    for class_id in PLAYABLE_CLASSES:
        label = engine.get_display_name("class", class_id, locale=locale) or class_id
        incant = "INT" if class_id == "wizard" else "SAG"
        options.append(
            discord.SelectOption(
                label=label[:100],
                value=class_id,
                description=f"Incantation {incant} — sorts actifs",
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
