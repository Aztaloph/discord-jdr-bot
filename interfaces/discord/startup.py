# interfaces/discord/startup.py
"""Initialisation Rule Engine + CharacterService au démarrage du bot."""
from __future__ import annotations

import logging

from jdr_engine.application.character_service import CharacterService
from jdr_engine.persistence.character_repository import JsonCharacterRepository
from jdr_engine.rules.engine import RuleEngine

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.settings import DiscordSettings

logger = logging.getLogger(__name__)


def init_discord_jdr(config: dict | None = None) -> DiscordJdrContext:
    """
    Charge le moteur v2 si USE_ENGINE_V2 est activé.
    Valide le Compendium au démarrage (strict configurable).
    """
    settings = DiscordSettings.from_config(config)
    ctx = DiscordJdrContext(settings=settings)

    if not settings.use_engine_v2:
        logger.info("Moteur v2 désactivé (USE_ENGINE_V2=false). Mode legacy.")
        return ctx

    try:
        engine = RuleEngine.load(
            settings.default_ruleset,
            validate=True,
            strict=settings.compendium_strict,
        )
        repo = JsonCharacterRepository()
        service = CharacterService(repo, engine)
        ctx.rule_engine = engine
        ctx.character_service = service
        logger.info(
            "Moteur v2 activé — ruleset=%s@%s, %d entrées Compendium",
            engine.ruleset_id,
            engine.ruleset_version,
            len(engine.registry),
        )
    except Exception as exc:
        logger.error("Échec init moteur v2 : %s — fallback legacy", exc)
        ctx.settings = DiscordSettings(
            use_engine_v2=False,
            default_ruleset=settings.default_ruleset,
            default_locale=settings.default_locale,
            compendium_strict=settings.compendium_strict,
        )

    return ctx
