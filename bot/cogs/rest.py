# bot/cogs/rest.py
"""Cog Discord — repos long / court (MJ uniquement, SRD 2014)."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from interfaces.discord.handlers import mj_rest as mj_rest_handler
from interfaces.discord.handlers import mj_level_up as mj_level_up_handler
from interfaces.discord.handlers import mj_grimoire as mj_grimoire_handler
from interfaces.discord.handlers.mj_delete import guild_character_autocomplete

log = logging.getLogger(__name__)


class RestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        log.info("RestCog initialisé.")

    @property
    def _jdr(self):
        return getattr(self.bot, "jdr", None)

    async def _personnage_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        ctx = self._jdr
        if ctx is None or not ctx.use_engine_v2:
            return []
        return await guild_character_autocomplete(interaction, current, ctx)

    @app_commands.command(
        name="repos-long",
        description="[MJ] Repos long (8 h) — PV max, dés de vie, emplacements de sorts",
    )
    @app_commands.describe(
        personnage="Personnage ciblé (nom ou id court, ex. marie001)",
    )
    @app_commands.autocomplete(personnage=_personnage_autocomplete)
    async def repos_long(self, interaction: discord.Interaction, personnage: str):
        ctx = self._jdr
        if ctx is None or not ctx.use_engine_v2:
            await interaction.response.send_message(
                "Moteur v2 requis.", ephemeral=True
            )
            return
        await mj_rest_handler.mj_repos_long(interaction, ctx, personnage)

    @app_commands.command(
        name="repos-court",
        description="[MJ] Repos court (1 h) — dépense des dés de vie pour récupérer des PV",
    )
    @app_commands.describe(
        personnage="Personnage ciblé (nom ou id court)",
        des="Nombre de dés de vie à dépenser (0 = repos sans soin)",
    )
    @app_commands.autocomplete(personnage=_personnage_autocomplete)
    async def repos_court(
        self,
        interaction: discord.Interaction,
        personnage: str,
        des: app_commands.Range[int, 0, 20] = 1,
    ):
        ctx = self._jdr
        if ctx is None or not ctx.use_engine_v2:
            await interaction.response.send_message(
                "Moteur v2 requis.", ephemeral=True
            )
            return
        await mj_rest_handler.mj_repos_court(interaction, ctx, personnage, des)

    @app_commands.command(
        name="monter-niveau",
        description="[MJ] Monte un personnage d'un niveau (toutes classes, niv. 2–3)",
    )
    @app_commands.describe(
        personnage="Personnage ciblé (nom ou id court, ex. marie001)",
    )
    @app_commands.autocomplete(personnage=_personnage_autocomplete)
    async def monter_niveau(self, interaction: discord.Interaction, personnage: str):
        ctx = self._jdr
        if ctx is None or not ctx.use_engine_v2:
            await interaction.response.send_message(
                "Moteur v2 requis.", ephemeral=True
            )
            return
        await mj_level_up_handler.mj_monter_niveau(interaction, ctx, personnage)

    @app_commands.command(
        name="reset-grimoire",
        description="[MJ] Réinitialise le grimoire d'un magicien (persos legacy / données polluées)",
    )
    @app_commands.describe(
        personnage="Magicien ciblé (nom ou id court, ex. joe00001)",
    )
    @app_commands.autocomplete(personnage=_personnage_autocomplete)
    async def reset_grimoire(self, interaction: discord.Interaction, personnage: str):
        ctx = self._jdr
        if ctx is None or not ctx.use_engine_v2:
            await interaction.response.send_message(
                "Moteur v2 requis.", ephemeral=True
            )
            return
        await mj_grimoire_handler.mj_reset_grimoire(interaction, ctx, personnage)


async def setup(bot: commands.Bot):
    await bot.add_cog(RestCog(bot))
