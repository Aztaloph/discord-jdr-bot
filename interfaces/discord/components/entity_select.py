# interfaces/discord/components/entity_select.py
"""Selects Discord générés depuis le Compendium."""
from __future__ import annotations

import discord

from jdr_engine.compendium.entry import EntitySummary
from jdr_engine.rules.engine import RuleEngine


def build_select_options(
    entities: list[EntitySummary],
    locale: str = "fr",
    *,
    fallback_locale: str = "en",
) -> list[discord.SelectOption]:
    options: list[discord.SelectOption] = []
    for entity in entities[:25]:
        label = entity.display_name(locale, fallback_locale)
        if len(label) > 100:
            label = label[:97] + "..."
        options.append(
            discord.SelectOption(
                label=label,
                value=entity.entry_id,
                description=entity.entry_id[:100],
            )
        )
    return options


def race_select_options(engine: RuleEngine, locale: str = "fr") -> list[discord.SelectOption]:
    return build_select_options(engine.list_entities("race"), locale)


def class_select_options(engine: RuleEngine, locale: str = "fr") -> list[discord.SelectOption]:
    return build_select_options(engine.list_entities("class"), locale)
