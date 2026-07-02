# interfaces/discord/container.py
"""Services Discord injectés dans le bot."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.application.character_service import CharacterService
from jdr_engine.rules.engine import RuleEngine

from interfaces.discord.settings import DiscordSettings


@dataclass
class DiscordJdrContext:
    settings: DiscordSettings
    rule_engine: RuleEngine | None = None
    character_service: CharacterService | None = None

    @property
    def use_engine_v2(self) -> bool:
        return (
            self.settings.use_engine_v2
            and self.rule_engine is not None
            and self.character_service is not None
        )

    @property
    def locale(self) -> str:
        return self.settings.default_locale
