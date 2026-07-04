# bot/cogs/racial.py
"""Cog Discord — actions raciales SRD 2014 (/souffle)."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from jdr_engine.dice import DiceError
from interfaces.discord.handlers.breath_weapon import (
    build_breath_embed,
    execute_breath_weapon,
)
from interfaces.discord.handlers.character import character_name_autocomplete

log = logging.getLogger(__name__)

COLOR_ERROR = discord.Color(0xF44336)


class RacialCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        log.info("RacialCog initialisé.")

    async def _perso_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        ctx = getattr(self.bot, "jdr", None)
        if ctx is None or not ctx.use_engine_v2:
            return []
        return await character_name_autocomplete(interaction, current, ctx)

    @app_commands.command(
        name="souffle",
        description="Utilise le souffle draconique (Drakéide uniquement, SRD 2014)",
    )
    @app_commands.describe(
        perso="Personnage (optionnel — utilise le perso actif par défaut)",
    )
    @app_commands.autocomplete(perso=_perso_autocomplete)
    async def souffle_cmd(
        self,
        interaction: discord.Interaction,
        perso: str | None = None,
    ):
        await interaction.response.defer(thinking=True)
        ctx = self.bot.jdr  # type: ignore[attr-defined]
        guild_id = str(interaction.guild.id) if interaction.guild else None
        try:
            result = execute_breath_weapon(
                ctx,
                owner_id=interaction.user.id,
                perso=perso,
                guild_id=guild_id,
            )
        except DiceError as exc:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Souffle impossible",
                    description=str(exc),
                    color=COLOR_ERROR,
                ).set_footer(text="JDR Bot — D&D 5e SRD 2014"),
                ephemeral=True,
            )
            return
        await interaction.followup.send(embed=build_breath_embed(result))


async def setup(bot: commands.Bot):
    await bot.add_cog(RacialCog(bot))
