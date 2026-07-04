# bot/cogs/creation.py
"""Cog Discord — création de personnage /creer-perso (ÉTAPE 1b)."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from interfaces.discord.views.creer_perso_wizard import start_creer_perso_wizard

log = logging.getLogger(__name__)


class CreationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        log.info("CreationCog initialisé.")

    @app_commands.command(
        name="creer-perso",
        description="Créer votre personnage (Magicien ou Clerc, SRD 2014)",
    )
    async def creer_perso(self, interaction: discord.Interaction):
        ctx = getattr(self.bot, "jdr", None)
        if ctx is None or not ctx.use_engine_v2:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Moteur v2 requis",
                    description="La création de personnage nécessite le moteur v2.",
                    color=0xF44336,
                ).set_footer(text="JDR Bot — D&D 5e SRD 2014"),
                ephemeral=True,
            )
            return
        await start_creer_perso_wizard(interaction, ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(CreationCog(bot))
